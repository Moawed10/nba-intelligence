"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { TeamMark } from "@/components/brand/team-mark";
import { CompareBar } from "@/components/data/compare-bar";
import { SegmentedControl } from "@/components/data/segmented-control";
import { Unavailable } from "@/components/data/unavailable";
import { clientGet } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import type { BoxScore, GamePage, GameSummary, Leaders, TeamSeasonStats } from "@/lib/api/types";
import { formatGameDate, formatGameTime, formatStat } from "@/lib/format";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

function shiftDate(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function statusLabel(game: GameSummary): string {
  if (game.status === "final") return "Final";
  if (game.status === "in_progress") return "In progress";
  if (game.status === "postponed") return "Postponed";
  if (game.status === "cancelled") return "Cancelled";
  return game.tipoff_at ? formatGameTime(game.tipoff_at) : "Time to be announced";
}

const ROUND_BUTTON =
  "inline-flex size-9 items-center justify-center rounded-full border border-border transition-colors hover:border-foreground/25";

function GameChip({
  game,
  selected,
  onSelect,
}: {
  game: GameSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  const final = game.status === "final";
  const homeWon = final && (game.home.score ?? 0) > (game.away.score ?? 0);
  const row = (side: "away" | "home") => {
    const entry = game[side];
    const won = final && (side === "home" ? homeWon : !homeWon);
    return (
      <span className="flex items-center gap-2">
        <TeamMark team={entry.team} size="xs" />
        <span className={cn("flex-1 text-left", won && "font-semibold")}>{entry.team.abbreviation}</span>
        {final && (
          <span className={cn("tabular-nums", won ? "font-semibold" : "text-muted-foreground")}>
            {entry.score}
          </span>
        )}
      </span>
    );
  };
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "flex w-40 shrink-0 snap-start flex-col gap-1.5 rounded-xl border px-3 py-2.5 text-subhead transition-colors",
        selected ? "border-primary/70 bg-primary/10" : "border-border bg-card hover:border-foreground/25",
      )}
    >
      <span className="sr-only">
        {game.away.team.city} at {game.home.team.city},{" "}
      </span>
      <span className="kicker text-left">{statusLabel(game)}</span>
      {row("away")}
      {row("home")}
    </button>
  );
}

function TeamColumn({ game, side }: { game: GameSummary; side: "away" | "home" }) {
  const entry = game[side];
  return (
    <div
      className={cn("relative flex flex-col items-center gap-2 text-center", side === "home" && "md:order-3")}
    >
      <TeamMark team={entry.team} size="lg" />
      <div>
        <p className="kicker">{side === "home" ? "Home" : "Away"}</p>
        <p className="text-headline font-semibold">
          {entry.team.city} {entry.team.name}
        </p>
      </div>
      {entry.score != null && (
        <p className="text-[2.5rem] leading-none font-semibold tabular-nums">{entry.score}</p>
      )}
    </div>
  );
}

function Matchup({ game }: { game: GameSummary }) {
  const stats = useQuery({
    queryKey: ["matchup-stats", game.away.team.id, game.home.team.id, game.season],
    queryFn: ({ signal }) =>
      Promise.all(
        [game.away.team.id, game.home.team.id].map((id) =>
          clientGet<TeamSeasonStats>(`/teams/${id}/stats`, { season: game.season }, signal),
        ),
      ),
  });
  const box = useQuery({
    queryKey: ["boxscore", game.id],
    queryFn: ({ signal }) => clientGet<BoxScore>(`/games/${game.id}/boxscore`, undefined, signal),
    enabled: game.status === "final",
  });
  const [away, home] = stats.data ?? [];
  const names: [string, string] = [game.away.team.name, game.home.team.name];
  const record = (s?: TeamSeasonStats) => (s ? `${s.record.wins}–${s.record.losses}` : "—");

  return (
    <div className="space-y-5">
      <div className="relative grid grid-cols-2 items-center gap-4 overflow-hidden rounded-xl border border-border p-5 md:grid-cols-[1fr_auto_1fr]">
        <div
          aria-hidden
          className="absolute inset-0 opacity-25"
          style={{
            background: `linear-gradient(90deg, ${game.away.team.primary_color ?? "transparent"} 0%, transparent 45%, transparent 55%, ${game.home.team.primary_color ?? "transparent"} 100%)`,
          }}
        />
        <TeamColumn game={game} side="away" />
        <div className="relative order-last col-span-2 text-center md:order-none md:col-span-1">
          <p className="kicker">{statusLabel(game)}</p>
          <p className="text-footnote text-muted-foreground">
            {formatGameDate(game.game_date, true)}
            {game.arena ? ` · ${game.arena}` : ""}
          </p>
        </div>
        <TeamColumn game={game} side="home" />
      </div>

      {stats.error ? (
        <Unavailable kind="error" title="Team statistics couldn't load">
          {describeError(stats.error).message}
        </Unavailable>
      ) : (
        <div className="space-y-3" aria-busy={stats.isPending}>
          <p className="kicker">{game.season} regular season</p>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-x-3 text-headline tabular-nums">
            <span className="text-right">{record(away)}</span>
            <span className="text-footnote text-muted-foreground">Record</span>
            <span>{record(home)}</span>
          </div>
          <CompareBar
            label="Offensive rating"
            left={away?.offensive_rating ?? null}
            right={home?.offensive_rating ?? null}
            format={formatStat}
            names={names}
          />
          <CompareBar
            label="Defensive rating"
            left={away?.defensive_rating ?? null}
            right={home?.defensive_rating ?? null}
            format={formatStat}
            better="lower"
            names={names}
          />
          <CompareBar
            label="Pace"
            left={away?.pace ?? null}
            right={home?.pace ?? null}
            format={formatStat}
            better="neither"
          />
          <p className="text-footnote text-muted-foreground">
            Points scored and allowed per 100 possessions; a lower defensive rating is better.
          </p>
        </div>
      )}

      {game.status === "final" && box.data && (
        <div className="grid gap-3 sm:grid-cols-2">
          {box.data.teams.map((team) => {
            const top = [...team.players].sort((a, b) => b.box.pts - a.box.pts)[0];
            if (!top) return null;
            return (
              <Link
                key={team.team.id}
                href={`/players/${top.player_id}`}
                className="flex items-center gap-3 rounded-xl border border-border p-3 transition-colors hover:border-foreground/25"
              >
                <PlayerAvatar name={top.full_name} team={team.team} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="kicker block">{team.team.abbreviation} top scorer</span>
                  <span className="block truncate font-medium">{top.full_name}</span>
                </span>
                <span className="text-right tabular-nums">
                  <span className="block text-headline font-semibold">{top.box.pts}</span>
                  <span className="text-footnote text-muted-foreground">
                    {top.box.reb} reb · {top.box.ast} ast
                  </span>
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ScheduleBoard({
  initialDate,
  initialGames,
}: {
  initialDate: string;
  initialGames: GameSummary[];
}) {
  const [date, setDate] = useState(initialDate);
  const [selectedId, setSelectedId] = useState<string | null>(initialGames[0]?.id ?? null);
  const games = useQuery({
    queryKey: ["games-day", date],
    queryFn: ({ signal }) =>
      clientGet<GamePage>("/games", { date_from: date, date_to: date, limit: 20 }, signal).then(
        (p) => p.items,
      ),
    initialData: date === initialDate ? initialGames : undefined,
    staleTime: 60_000,
  });
  const list = games.data ?? [];
  const selected = list.find((g) => g.id === selectedId) ?? list[0] ?? null;

  function move(days: number) {
    setDate((d) => shiftDate(d, days));
    setSelectedId(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => move(-1)} aria-label="Previous day" className={ROUND_BUTTON}>
            <ChevronLeft aria-hidden className="size-4" />
          </button>
          <p className="min-w-32 text-center text-headline font-semibold tabular-nums" aria-live="polite">
            {formatGameDate(date, true)}
          </p>
          <button type="button" onClick={() => move(1)} aria-label="Next day" className={ROUND_BUTTON}>
            <ChevronRight aria-hidden className="size-4" />
          </button>
        </div>
        <p className="text-footnote text-muted-foreground">
          {games.isFetching ? "Loading games…" : `${list.length} ${list.length === 1 ? "game" : "games"}`}
        </p>
      </div>

      {games.error ? (
        <Unavailable kind="error" title="The schedule couldn't load">
          {describeError(games.error).message}
        </Unavailable>
      ) : list.length === 0 && !games.isFetching ? (
        <Unavailable kind="no_games" title={`No games on ${formatGameDate(date, true)}`}>
          Use the arrows to browse other days. Dates follow the NBA&apos;s published schedule.
        </Unavailable>
      ) : (
        <div
          role="group"
          aria-label="Games on this day"
          className="-mx-4 flex snap-x gap-2 overflow-x-auto px-4 pb-1 sm:-mx-5 sm:px-5"
        >
          {list.map((game) => (
            <GameChip
              key={game.id}
              game={game}
              selected={selected?.id === game.id}
              onSelect={() => setSelectedId(game.id)}
            />
          ))}
        </div>
      )}
      {selected && <Matchup key={selected.id} game={selected} />}
    </div>
  );
}

const LEADER_STATS = [
  { value: "pts", label: "PTS", unit: "Points" },
  { value: "reb", label: "REB", unit: "Rebounds" },
  { value: "ast", label: "AST", unit: "Assists" },
  { value: "fg3m", label: "3PM", unit: "3-pointers made" },
  { value: "stl", label: "STL", unit: "Steals" },
  { value: "blk", label: "BLK", unit: "Blocks" },
] as const;
type LeaderStat = (typeof LEADER_STATS)[number]["value"];

export function LeadersBoard({ initial }: { initial: Leaders }) {
  const [stat, setStat] = useState<LeaderStat>("pts");
  const leaders = useQuery({
    queryKey: ["leaders", stat, initial.season],
    queryFn: ({ signal }) =>
      clientGet<Leaders>("/leaders", { stat, season: initial.season, limit: 5 }, signal),
    initialData: stat === "pts" ? initial : undefined,
    placeholderData: (previous) => previous,
    staleTime: 5 * 60_000,
  });
  const data = leaders.data;
  const unit = LEADER_STATS.find((s) => s.value === stat)!.unit;
  const top = data?.leaders[0]?.value || 1;

  return (
    <div className="space-y-4">
      <div className="-mx-1 overflow-x-auto px-1">
        <SegmentedControl
          label="Leader category"
          value={stat}
          onChange={setStat}
          segments={LEADER_STATS.map((s) => ({ value: s.value, label: s.label }))}
        />
      </div>
      {leaders.error ? (
        <Unavailable kind="error" title="Leaders couldn't load">
          {describeError(leaders.error).message}
        </Unavailable>
      ) : data && data.leaders.length === 0 ? (
        <Unavailable kind="empty" title="No qualified players yet">
          Leaders need at least {data.minimum_games} games played.
        </Unavailable>
      ) : (
        <ol className="space-y-1" aria-busy={leaders.isFetching} aria-label={`${unit} per game leaders`}>
          {data?.leaders.map((leader) => (
            <motion.li key={leader.player_id} layout="position" transition={SPRING.snappy}>
              <Link
                href={`/players/${leader.player_id}`}
                className="group flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-muted"
              >
                <span className="w-4 text-right text-footnote text-muted-foreground tabular-nums">
                  {leader.rank}
                </span>
                <PlayerAvatar name={leader.full_name} team={leader.team} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium group-hover:text-primary">
                    {leader.full_name}
                  </span>
                  <span aria-hidden className="mt-1 block h-1 overflow-hidden rounded-full bg-muted">
                    <span
                      className="block h-full rounded-full bg-primary/80 transition-[width] duration-500"
                      style={{ width: `${(leader.value / top) * 100}%` }}
                    />
                  </span>
                </span>
                <span className="text-right">
                  <span className="block text-headline font-semibold tabular-nums">
                    {formatStat(leader.value)}
                  </span>
                  <span className="text-footnote text-muted-foreground">
                    {leader.team?.abbreviation ?? "—"} · {leader.games_played} GP
                  </span>
                </span>
              </Link>
            </motion.li>
          ))}
        </ol>
      )}
      {data && (
        <p className="text-footnote text-muted-foreground">
          {unit} per game, {data.season} regular season. Qualified players have at least {data.minimum_games}{" "}
          games ({data.qualified_players} players).
        </p>
      )}
    </div>
  );
}
