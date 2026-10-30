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
import { clientGet, clientPost } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import type {
  BoxScore,
  BoxScorePlayer,
  GameForecast,
  GameForecastResult,
  GameForecastReview,
  GamePage,
  GameSummary,
  Leaders,
  TeamSeasonStats,
} from "@/lib/api/types";
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
  forecast,
  selected,
  onSelect,
}: {
  game: GameSummary;
  forecast: GameForecast | null;
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
          <span className={cn("numeral text-headline", won ? "text-foreground" : "text-muted-foreground")}>
            {entry.score}
          </span>
        )}
        {!final && forecast && (
          <span className="numeral text-headline text-muted-foreground">
            <span className="sr-only">predicted </span>
            {Math.round(forecast[side].points)}
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
        "relative flex w-40 shrink-0 snap-start flex-col gap-1.5 rounded-xl border px-3 py-2.5 text-subhead transition-colors",
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
  const other = game[side === "home" ? "away" : "home"];
  const lost = game.status === "final" && (entry.score ?? 0) < (other.score ?? 0);
  return (
    <div
      className={cn("relative flex flex-col items-center gap-2 text-center", side === "home" && "md:order-3")}
    >
      <TeamMark team={entry.team} size="xl" className="max-sm:size-14" />
      <div>
        <p className="kicker">{side === "home" ? "Home" : "Away"}</p>
        <p className="font-[family-name:var(--font-display)] text-title2 leading-tight font-extrabold uppercase">
          {entry.team.city} {entry.team.name}
        </p>
      </div>
      {entry.score != null && (
        <p className={cn("numeral text-[clamp(3rem,7vw,4.5rem)]", lost && "text-muted-foreground")}>
          {entry.score}
        </p>
      )}
    </div>
  );
}

function Matchup({
  game,
  fullBox,
  forecast,
  pageLink = true,
}: {
  game: GameSummary;
  fullBox?: boolean;
  forecast?: { result: GameForecastResult | undefined; pending: boolean; error: unknown };
  /** Show a link to the game's own page (off on that page). */
  pageLink?: boolean;
}) {
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
          {pageLink && (
            <Link
              href={`/games/${game.id}`}
              className="mt-2 inline-flex min-h-9 items-center text-subhead font-medium text-primary hover:underline"
            >
              Game page
            </Link>
          )}
        </div>
        <TeamColumn game={game} side="home" />
      </div>

      {game.status === "scheduled" && forecast && <ScoreForecast game={game} {...forecast} />}
      {game.status === "final" && <PredictionReview game={game} />}
      {game.status === "scheduled" && <PlayerShortcuts game={game} />}

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

      {game.status === "final" && box.error && (
        <Unavailable kind="error" title="The box score couldn't load">
          {describeError(box.error).message}
        </Unavailable>
      )}
      {fullBox && game.status === "final" && box.data && <BoxScoreTables box={box.data} />}
      {!fullBox && game.status === "final" && box.data && (
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
                <PlayerAvatar id={top.player_id} name={top.full_name} team={team.team} size="sm" />
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

/** The pregame score prediction in plain language: expected score, win chance and a typical range. */
function ScoreForecast({
  game,
  result,
  pending,
  error,
}: {
  game: GameSummary;
  result: GameForecastResult | undefined;
  pending: boolean;
  error: unknown;
}) {
  if (error) {
    return (
      <Unavailable kind="error" title="The score prediction couldn't load">
        {describeError(error).message}
      </Unavailable>
    );
  }
  if (pending || !result) {
    return (
      <div aria-busy className="h-56 animate-pulse rounded-xl border border-border">
        <span className="sr-only">Loading the score prediction</span>
      </div>
    );
  }
  if (!result.forecast) {
    return (
      <Unavailable kind="empty" title="No score prediction for this game">
        {result.unavailable?.message}
      </Unavailable>
    );
  }
  const f = result.forecast;
  const away = { team: game.away.team, ...f.away, chance: 1 - f.home_win_probability };
  const home = { team: game.home.team, ...f.home, chance: f.home_win_probability };
  const [favorite, underdog] = home.chance >= 0.5 ? [home, away] : [away, home];
  const margin = Math.round(favorite.points - underdog.points);
  const pct = (p: number) => `${Math.round(p * 100)}%`;
  const headline =
    favorite.chance < 0.55
      ? "Close to a coin flip"
      : `${favorite.team.name} favored${margin > 0 ? ` by about ${margin}` : ""}`;

  return (
    <section
      aria-labelledby={`forecast-${game.id}`}
      className="space-y-4 rounded-xl border border-border p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`forecast-${game.id}`} className="kicker text-primary">
          Our prediction
        </h3>
        <p className="text-footnote text-muted-foreground">Made before tip-off</p>
      </div>
      <p className="font-[family-name:var(--font-display)] text-title2 leading-tight font-extrabold uppercase">
        {headline}
      </p>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        {[away, home].map((side, i) => (
          <div
            key={side.team.id}
            className={cn(
              "flex min-w-0 items-center gap-3",
              i === 1 && "order-3 flex-row-reverse text-right",
            )}
          >
            <TeamMark team={side.team} size="md" />
            <div className="min-w-0">
              <p className="truncate text-subhead text-muted-foreground">{side.team.name}</p>
              <p className="numeral text-[clamp(2.25rem,5vw,3rem)]">{Math.round(side.points)}</p>
            </div>
          </div>
        ))}
        <span aria-hidden className="order-2 text-title3 text-muted-foreground">
          –
        </span>
      </div>
      <div>
        <div className="flex items-baseline justify-between gap-2 text-subhead font-medium tabular-nums">
          <span>
            {away.team.name} {pct(away.chance)}
          </span>
          <span className="text-footnote text-muted-foreground">Chance to win</span>
          <span>
            {home.team.name} {pct(home.chance)}
          </span>
        </div>
        <div
          role="img"
          aria-label={`Chance to win: ${away.team.name} ${pct(away.chance)}, ${home.team.name} ${pct(home.chance)}`}
          className="mt-2 flex h-2.5 gap-0.5"
        >
          <motion.span
            className="h-full rounded-l-full"
            style={{ background: away.team.primary_color ?? "var(--muted-foreground)" }}
            initial={{ width: "50%" }}
            animate={{ width: pct(away.chance) }}
            transition={SPRING}
          />
          <span
            className="h-full flex-1"
            style={{ background: home.team.primary_color ?? "var(--primary)" }}
          />
        </div>
      </div>
      <p className="text-subhead text-muted-foreground">
        Typical range: {away.team.name} {Math.round(away.lower)}–{Math.round(away.upper)}, {home.team.name}{" "}
        {Math.round(home.lower)}–{Math.round(home.upper)}. About {Math.round(f.interval_level * 10)} in 10
        games finish inside these ranges. The prediction looks at each team&apos;s last 10 games (points
        scored and allowed, efficiency, pace), its record this season, days of rest and home court, and only
        at games played before this one.
      </p>
    </section>
  );
}

/** A finished game: the score predicted before tip-off next to the final score. */
function PredictionReview({ game }: { game: GameSummary }) {
  const review = useQuery({
    queryKey: ["game-review", game.id],
    queryFn: ({ signal }) =>
      clientGet<GameForecastReview>(`/predictions/games/${game.id}`, undefined, signal),
  });
  const data = review.data;
  if (!data?.forecast || data.home_score == null || data.away_score == null) return null;
  const f = data.forecast;
  const sides = [
    { team: game.away.team, predicted: f.away, actual: data.away_score },
    { team: game.home.team, predicted: f.home, actual: data.home_score },
  ];
  const favorite = f.home_win_probability >= 0.5 ? game.home.team : game.away.team;
  const chance = Math.round(Math.max(f.home_win_probability, 1 - f.home_win_probability) * 100);
  return (
    <section aria-labelledby={`review-${game.id}`} className="space-y-4 rounded-xl border border-border p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`review-${game.id}`} className="kicker text-primary">
          How our prediction did
        </h3>
        <p
          className={cn("text-subhead font-semibold", data.picked_winner ? "text-positive" : "text-negative")}
        >
          {data.picked_winner ? "✓ Picked the winner" : "✗ Missed the winner"}
        </p>
      </div>
      <p className="text-subhead">
        Before tip-off we gave the {favorite.name} a {chance}% chance to win.
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {sides.map(({ team, predicted, actual }) => {
          const inside = actual >= predicted.lower && actual <= predicted.upper;
          return (
            <li key={team.id} className="flex items-center gap-3 rounded-xl bg-muted/40 p-3">
              <TeamMark team={team} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{team.name}</p>
                <p className="text-footnote text-muted-foreground">
                  Predicted {Math.round(predicted.points)} (usually {Math.round(predicted.lower)}–
                  {Math.round(predicted.upper)}) · {inside ? "inside the range" : "outside the range"}
                </p>
              </div>
              <p className="text-right">
                <span className="numeral block text-title2">{actual}</span>
                <span className="kicker">Final</span>
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const SHORTCUT_PLAYERS = 3;

/** Each team's leading scorers, each a shortcut to that player's forecast for this game. */
function PlayerShortcuts({ game }: { game: GameSummary }) {
  const teams = [game.away.team, game.home.team];
  const leaders = useQuery({
    queryKey: ["team-leaders", teams[0].id, teams[1].id],
    queryFn: ({ signal }) =>
      Promise.all(
        teams.map((t) =>
          clientGet<Leaders>("/leaders", { stat: "pts", team_id: t.id, limit: SHORTCUT_PLAYERS }, signal),
        ),
      ),
    staleTime: 5 * 60_000,
  });
  if (leaders.error || (leaders.data && leaders.data.every((l) => l.leaders.length === 0))) return null;
  return (
    <section aria-labelledby={`shortcuts-${game.id}`} className="space-y-3">
      <h3 id={`shortcuts-${game.id}`} className="kicker">
        Predict a player in this game
      </h3>
      <div className="grid gap-3 sm:grid-cols-2" aria-busy={leaders.isPending}>
        {teams.map((team, i) => (
          <ul key={team.id} className="space-y-2" aria-label={`${team.city} ${team.name} leading scorers`}>
            {(leaders.data?.[i].leaders ?? []).map((l) => (
              <li key={l.player_id}>
                <Link
                  href={`/predict?player=${l.player_id}&game=${game.id}`}
                  className="flex items-center gap-3 rounded-xl border border-border p-3 transition-colors hover:border-foreground/25"
                >
                  <PlayerAvatar id={l.player_id} name={l.full_name} team={team} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{l.full_name}</span>
                    <span className="text-footnote text-muted-foreground">
                      {formatStat(l.value)} points per game
                    </span>
                  </span>
                  <span className="text-subhead font-medium text-primary">Forecast</span>
                </Link>
              </li>
            ))}
          </ul>
        ))}
      </div>
    </section>
  );
}

/** One game on its own page: the matchup with its score forecast when it is still to be played. */
export function GameMatchup({ game }: { game: GameSummary }) {
  const scheduled = game.status === "scheduled";
  const forecasts = useQuery({
    queryKey: ["game-forecasts", [game.id]],
    queryFn: () => clientPost<GameForecastResult[]>("/predictions/games", { game_ids: [game.id] }),
    enabled: scheduled,
    staleTime: 5 * 60_000,
  });
  return (
    <Matchup
      game={game}
      fullBox
      pageLink={false}
      forecast={
        scheduled
          ? { result: forecasts.data?.[0], pending: forecasts.isPending, error: forecasts.error }
          : undefined
      }
    />
  );
}

const BOX_COLUMNS = [
  { label: "MIN", title: "Minutes", value: (p: BoxScorePlayer) => p.minutes.toFixed(0) },
  { label: "PTS", title: "Points", value: (p: BoxScorePlayer) => p.box.pts },
  { label: "REB", title: "Rebounds", value: (p: BoxScorePlayer) => p.box.reb },
  { label: "AST", title: "Assists", value: (p: BoxScorePlayer) => p.box.ast },
  { label: "STL", title: "Steals", value: (p: BoxScorePlayer) => p.box.stl },
  { label: "BLK", title: "Blocks", value: (p: BoxScorePlayer) => p.box.blk },
  { label: "TO", title: "Turnovers", value: (p: BoxScorePlayer) => p.box.tov },
  {
    label: "FG",
    title: "Field goals made–attempted",
    value: (p: BoxScorePlayer) => `${p.box.fgm}–${p.box.fga}`,
  },
  {
    label: "3P",
    title: "3-pointers made–attempted",
    value: (p: BoxScorePlayer) => `${p.box.fg3m}–${p.box.fg3a}`,
  },
  {
    label: "FT",
    title: "Free throws made–attempted",
    value: (p: BoxScorePlayer) => `${p.box.ftm}–${p.box.fta}`,
  },
  {
    label: "+/−",
    title: "Plus-minus",
    value: (p: BoxScorePlayer) =>
      p.box.plus_minus == null ? "—" : p.box.plus_minus > 0 ? `+${p.box.plus_minus}` : p.box.plus_minus,
  },
];

function BoxScoreTables({ box }: { box: BoxScore }) {
  return (
    <div className="space-y-6">
      {!box.stats_finalized && (
        <p className="text-footnote text-muted-foreground">
          Box score not finalized by the source yet; numbers may still change.
        </p>
      )}
      {box.teams.map((team) => (
        <div
          key={team.team.id}
          role="region"
          aria-label={`${team.team.city} ${team.team.name} box score`}
          tabIndex={0}
          className="overflow-x-auto"
        >
          <table className="w-full min-w-[40rem] text-subhead tabular-nums">
            <caption className="mb-2 text-left font-semibold">
              {team.team.city} {team.team.name}
            </caption>
            <thead className="text-footnote text-muted-foreground">
              <tr className="border-b border-border">
                <th scope="col" className="py-1.5 text-left font-medium">
                  Player
                </th>
                {BOX_COLUMNS.map((c) => (
                  <th key={c.label} scope="col" className="py-1.5 text-right font-medium">
                    <abbr title={c.title} className="no-underline">
                      {c.label}
                    </abbr>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...team.players]
                .sort((a, b) => b.minutes - a.minutes)
                .map((p) => (
                  <tr key={p.player_id} className="border-b border-border/50">
                    <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                      <Link href={`/players/${p.player_id}`} className="hover:text-primary">
                        {p.full_name}
                      </Link>
                    </th>
                    {BOX_COLUMNS.map((c) => (
                      <td key={c.label} className="py-1.5 text-right">
                        {c.value(p)}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
            <tfoot>
              <tr className="font-semibold">
                <th scope="row" className="py-1.5 text-left">
                  Team
                </th>
                <td className="py-1.5 text-right">{team.minutes}</td>
                {[
                  team.totals.pts,
                  team.totals.reb,
                  team.totals.ast,
                  team.totals.stl,
                  team.totals.blk,
                  team.totals.tov,
                  `${team.totals.fgm}–${team.totals.fga}`,
                  `${team.totals.fg3m}–${team.totals.fg3a}`,
                  `${team.totals.ftm}–${team.totals.fta}`,
                  "",
                ].map((v, i) => (
                  <td key={i} className="py-1.5 text-right">
                    {v}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      ))}
    </div>
  );
}

export function ScheduleBoard({
  initialDate,
  initialGames,
  fullBox,
  urlPath,
}: {
  initialDate: string;
  initialGames: GameSummary[];
  /** Full box scores for final games instead of the top-scorer summary. */
  fullBox?: boolean;
  /** Mirror the browsed date into `?date=` on this path so the day can be linked. */
  urlPath?: string;
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
  const upcoming = list.filter((g) => g.status === "scheduled").map((g) => g.id);
  const forecasts = useQuery({
    queryKey: ["game-forecasts", upcoming],
    queryFn: () => clientPost<GameForecastResult[]>("/predictions/games", { game_ids: upcoming }),
    enabled: upcoming.length > 0,
    staleTime: 5 * 60_000,
    select: (rows) => new Map(rows.map((r) => [r.game_id, r])),
  });

  function move(days: number) {
    const next = shiftDate(date, days);
    setDate(next);
    setSelectedId(null);
    if (urlPath) window.history.replaceState(null, "", `${urlPath}?date=${next}`);
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
              forecast={forecasts.data?.get(game.id)?.forecast ?? null}
              selected={selected?.id === game.id}
              onSelect={() => setSelectedId(game.id)}
            />
          ))}
        </div>
      )}
      {forecasts.data && forecasts.data.size > 0 && (
        <p className="text-footnote text-muted-foreground">
          Grey scores on upcoming games are our predictions. Pick a game to see who&apos;s favored and why.
        </p>
      )}
      {selected && (
        <Matchup
          key={selected.id}
          game={selected}
          fullBox={fullBox}
          forecast={{
            result: forecasts.data?.get(selected.id),
            pending: forecasts.isPending,
            error: forecasts.error,
          }}
        />
      )}
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
                <PlayerAvatar id={leader.player_id} name={leader.full_name} team={leader.team} size="sm" />
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
