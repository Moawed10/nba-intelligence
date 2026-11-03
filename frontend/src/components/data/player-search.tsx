"use client";

import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Search, X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";

import { TeamMark } from "@/components/brand/team-mark";
import { clientGet } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import type { PlayerSearchResult, Team } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export const MIN_QUERY_LENGTH = 2;
export const SEARCH_DEBOUNCE_MS = 250;

function useDebounced(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function playerDetails(player: PlayerSearchResult): string {
  return [player.team_abbreviation, player.position, player.is_active ? null : "Former player"]
    .filter(Boolean)
    .join(" · ");
}

const fold = (text: string) => text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

/** Bolds the part of a name that matches the query, ignoring case and accents. */
export function highlight(name: string, query: string): ReactNode {
  const needle = fold(query.trim());
  if (!needle) return name;
  const chars = Array.from(name);
  const folded = chars.map(fold);
  for (let start = 0; start < folded.length; start++) {
    let end = start;
    let matched = "";
    while (end < folded.length && matched.length < needle.length) matched += folded[end++];
    if (matched === needle) {
      return (
        <>
          {chars.slice(0, start).join("")}
          <mark className="bg-transparent font-semibold text-primary">
            {chars.slice(start, end).join("")}
          </mark>
          {chars.slice(end).join("")}
        </>
      );
    }
  }
  return name;
}

interface PlayerSearchProps {
  label?: string;
  onSelect: (player: PlayerSearchResult) => void;
  className?: string;
  /** Show results as soon as they arrive, for a search the user has just opened. */
  startOpen?: boolean;
  /** "inline" keeps the results in the document flow, e.g. inside a dialog. */
  listMode?: "popover" | "inline";
  hideLabel?: boolean;
  /** Also match teams, listed above players; the list of 30 is filtered in the browser. */
  onSelectTeam?: (team: Team) => void;
}

/** WAI-ARIA combobox (list autocomplete) over GET /players/search. */
export function PlayerSearch({
  label = "Search players",
  onSelect,
  className,
  startOpen,
  listMode = "popover",
  hideLabel,
  onSelectTeam,
}: PlayerSearchProps) {
  const id = useId();
  const listId = `${id}-list`;
  const inputRef = useRef<HTMLInputElement>(null);
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(Boolean(startOpen));
  const [active, setActive] = useState(-1);
  const term = useDebounced(input.trim(), SEARCH_DEBOUNCE_MS);
  const enabled = term.length >= MIN_QUERY_LENGTH;

  const { data, error, isFetching } = useQuery({
    queryKey: ["player-search", term.toLowerCase()],
    queryFn: ({ signal }) =>
      clientGet<PlayerSearchResult[]>("/players/search", { q: term, limit: 10 }, signal),
    enabled,
    staleTime: 5 * 60_000,
  });

  const { data: allTeams } = useQuery({
    queryKey: ["teams"],
    queryFn: ({ signal }) => clientGet<Team[]>("/teams", undefined, signal),
    enabled: Boolean(onSelectTeam),
    staleTime: 60 * 60_000,
  });

  const players = enabled ? (data ?? []) : [];
  const needle = fold(term);
  const teams =
    enabled && onSelectTeam
      ? (allTeams ?? []).filter((t) => fold(`${t.city} ${t.name} ${t.abbreviation}`).includes(needle))
      : [];
  const count = teams.length + players.length;
  const typing = input.trim().length >= MIN_QUERY_LENGTH && input.trim() !== term;
  const loading = typing || (enabled && isFetching);
  const settled = enabled && input.trim() === term && !isFetching;
  const expanded = open && enabled && count > 0;

  function choose(player: PlayerSearchResult) {
    onSelect(player);
    setInput(player.full_name);
    setOpen(false);
    setActive(-1);
  }

  function chooseTeam(team: Team) {
    onSelectTeam?.(team);
    setInput(`${team.city} ${team.name}`);
    setOpen(false);
    setActive(-1);
  }

  function clear() {
    setInput("");
    setActive(-1);
    inputRef.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!count) return;
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + count) % count);
    } else if (event.key === "Enter" && expanded && active >= 0) {
      event.preventDefault();
      if (active < teams.length) chooseTeam(teams[active]);
      else choose(players[active - teams.length]);
    } else if (event.key === "Escape" && (expanded || input)) {
      event.preventDefault();
      event.stopPropagation();
      if (expanded) setOpen(false);
      else setInput("");
      setActive(-1);
    }
  }

  const typed = input.trim().length;
  let status = "";
  if (typed > 0 && typed < MIN_QUERY_LENGTH) {
    status = `Type at least ${MIN_QUERY_LENGTH} characters to search.`;
  } else if (settled && error) {
    status = describeError(error).message;
  } else if (settled) {
    const found = [
      teams.length ? `${teams.length} ${teams.length === 1 ? "team" : "teams"}` : null,
      players.length ? `${players.length} ${players.length === 1 ? "player" : "players"}` : null,
    ].filter(Boolean);
    status = found.length
      ? `${found.join(" and ")} found.`
      : onSelectTeam
        ? "No players or teams match that name."
        : "No players match that name.";
  }

  const Icon = loading ? LoaderCircle : Search;
  return (
    <div className={cn("relative w-full", className)}>
      <label htmlFor={id} className={cn("mb-2 block text-subhead font-medium", hideLabel && "sr-only")}>
        {label}
      </label>
      <div className="relative">
        <Icon
          aria-hidden
          className={cn(
            "pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground",
            loading && "animate-spin",
          )}
        />
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-activedescendant={expanded && active >= 0 ? `${listId}-${active}` : undefined}
          aria-describedby={`${id}-status`}
          aria-busy={loading}
          value={input}
          placeholder={onSelectTeam ? "Player or team" : "Player name"}
          onChange={(event) => {
            setInput(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => listMode === "popover" && setOpen(false)}
          onKeyDown={onKeyDown}
          className="h-11 w-full rounded-xl border border-input bg-card pr-10 pl-9 text-body transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
        />
        {input && (
          <button
            type="button"
            onClick={clear}
            aria-label="Clear search"
            className="absolute top-1/2 right-1.5 inline-flex size-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X aria-hidden className="size-4" />
          </button>
        )}
      </div>
      <p id={`${id}-status`} role="status" aria-live="polite" className="sr-only">
        {status}
      </p>
      {settled && open && (error != null || count === 0) && (
        <p className={cn("mt-2 text-subhead", error ? "text-negative" : "text-muted-foreground")}>{status}</p>
      )}
      <ul
        id={listId}
        role="listbox"
        aria-label={onSelectTeam ? "Matching players and teams" : "Matching players"}
        hidden={!expanded}
        className={cn(
          "mt-2 max-h-80 w-full overflow-y-auto p-1",
          listMode === "popover" &&
            "absolute z-20 rounded-xl border border-border bg-popover shadow-xl shadow-black/30",
        )}
      >
        {teams.map((team, index) => (
          // Keyboard selection happens on the combobox input via aria-activedescendant.
          // eslint-disable-next-line jsx-a11y/click-events-have-key-events
          <li
            key={`team-${team.id}`}
            id={`${listId}-${index}`}
            role="option"
            aria-selected={index === active}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => chooseTeam(team)}
            onMouseMove={() => setActive(index)}
            className={cn(
              "flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 transition-colors",
              index === active && "bg-accent text-accent-foreground",
            )}
          >
            <TeamMark size="xs" team={team} />
            <span className="min-w-0 flex-1 truncate">{highlight(`${team.city} ${team.name}`, input)}</span>
            <span
              className={cn(
                "shrink-0 text-footnote",
                index === active ? "text-accent-foreground" : "text-muted-foreground",
              )}
            >
              Team
            </span>
          </li>
        ))}
        {players.map((player, playerIndex) => {
          const index = playerIndex + teams.length;
          return (
            // Keyboard selection happens on the combobox input via aria-activedescendant.
            // eslint-disable-next-line jsx-a11y/click-events-have-key-events
            <li
              key={player.id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(player)}
              onMouseMove={() => setActive(index)}
              className={cn(
                "flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 transition-colors",
                index === active && "bg-accent text-accent-foreground",
              )}
            >
              <TeamMark
                size="xs"
                team={
                  player.team_abbreviation
                    ? {
                        id: player.team_id ?? 0,
                        abbreviation: player.team_abbreviation,
                        primary_color: player.team_primary_color ?? null,
                      }
                    : null
                }
              />
              <span className="min-w-0 flex-1 truncate">{highlight(player.full_name, input)}</span>
              <span
                className={cn(
                  "shrink-0 text-footnote",
                  index === active ? "text-accent-foreground" : "text-muted-foreground",
                )}
              >
                {playerDetails(player)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
