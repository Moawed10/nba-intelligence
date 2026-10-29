"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useState } from "react";

import { clientGet } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import type { PlayerSearchResult } from "@/lib/api/types";
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

interface PlayerSearchProps {
  label?: string;
  onSelect: (player: PlayerSearchResult) => void;
  className?: string;
}

/** WAI-ARIA combobox (list autocomplete) over GET /players/search. */
export function PlayerSearch({ label = "Search players", onSelect, className }: PlayerSearchProps) {
  const id = useId();
  const listId = `${id}-list`;
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);
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

  const results = enabled ? (data ?? []) : [];
  const settled = enabled && input.trim() === term && !isFetching;
  const expanded = open && enabled && results.length > 0;

  function choose(player: PlayerSearchResult) {
    onSelect(player);
    setInput(player.full_name);
    setOpen(false);
    setActive(-1);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!results.length) return;
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + results.length) % results.length);
    } else if (event.key === "Enter" && expanded && active >= 0) {
      event.preventDefault();
      choose(results[active]);
    } else if (event.key === "Escape") {
      event.preventDefault();
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
    status = results.length
      ? `${results.length} ${results.length === 1 ? "player" : "players"} found.`
      : "No players match that name.";
  }

  return (
    <div className={cn("relative w-full max-w-xl", className)}>
      <label htmlFor={id} className="mb-2 block text-subhead font-medium">
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <input
          id={id}
          type="search"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-activedescendant={expanded && active >= 0 ? `${listId}-${active}` : undefined}
          aria-describedby={`${id}-status`}
          value={input}
          placeholder="Player name"
          onChange={(event) => {
            setInput(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className="h-11 w-full rounded-xl border border-input bg-card pr-3 pl-9 text-body outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>
      <p id={`${id}-status`} role="status" aria-live="polite" className="sr-only">
        {status}
      </p>
      {settled && open && (error != null || results.length === 0) && (
        <p className={cn("mt-2 text-subhead", error ? "text-negative" : "text-muted-foreground")}>
          {status}
        </p>
      )}
      <ul
        id={listId}
        role="listbox"
        aria-label="Matching players"
        hidden={!expanded}
        className="absolute z-20 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-lg"
      >
        {results.map((player, index) => (
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
              "flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2",
              index === active && "bg-accent text-accent-foreground",
            )}
          >
            <span className="font-medium">{player.full_name}</span>
            <span
              className={cn(
                "shrink-0 text-footnote",
                index === active ? "text-accent-foreground" : "text-muted-foreground",
              )}
            >
              {playerDetails(player)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
