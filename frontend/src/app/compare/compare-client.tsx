"use client";

import { keepPreviousData, useQueries } from "@tanstack/react-query";
import { ArrowLeftRight, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { ChartFrame } from "@/components/data/chart-frame";
import { PlayerSearch } from "@/components/data/player-search";
import { SegmentedControl } from "@/components/data/segmented-control";
import { Unavailable } from "@/components/data/unavailable";
import { clientGet } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import type { PlayerTrends, TeamRef } from "@/lib/api/types";
import { formatGameValue, formatStat } from "@/lib/format";
import { hrefWith } from "@/lib/url";
import { cn } from "@/lib/utils";

import { TREND_STATS, type TrendStat } from "../players/[id]/stats";

export interface Picked {
  id: number;
  full_name: string;
  team: TeamRef | null;
  position: string | null;
}

const SLOT_COLORS = ["var(--chart-1)", "var(--chart-2)"] as const;
const ICON_BUTTON =
  "inline-flex size-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:border-foreground/25 hover:text-foreground pointer-coarse:size-11";

function useCompareNavigation(season?: string) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  function go(p1: number | undefined, p2: number | undefined, keepSeason = false) {
    startTransition(() =>
      router.push(hrefWith("/compare", {}, { p1, p2, season: keepSeason ? season : undefined }), {
        scroll: false,
      }),
    );
  }
  function setSeason(p1: number, p2: number, next: string) {
    startTransition(() => router.push(hrefWith("/compare", {}, { p1, p2, season: next }), { scroll: false }));
  }
  return { go, setSeason, pending };
}

/** Two player slots whose state lives in the URL (?p1=&p2=&season=), so comparisons can be shared. */
export function ComparePicker({
  players,
  season,
}: {
  players: [Picked | null, Picked | null];
  season?: string;
}) {
  const { go, pending } = useCompareNavigation(season);
  const [editing, setEditing] = useState<number | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const ids = players.map((p) => p?.id) as [number | undefined, number | undefined];

  function choose(slot: number, id: number) {
    if (id === ids[1 - slot]) {
      setDuplicate(true);
      return;
    }
    setDuplicate(false);
    setEditing(null);
    const next = [...ids];
    next[slot] = id;
    go(next[0], next[1]);
  }

  function remove(slot: number) {
    const next = [...ids];
    next[slot] = undefined;
    go(next[0], next[1]);
  }

  return (
    <div aria-busy={pending} className={cn("space-y-3 transition-opacity", pending && "opacity-70")}>
      <div className="grid items-stretch gap-3 md:grid-cols-[1fr_auto_1fr]">
        {[0, 1].map((slot) => {
          const player = players[slot];
          const label = `Player ${slot + 1}`;
          const body =
            player && editing !== slot ? (
              <div className="flex items-center gap-3">
                <PlayerAvatar name={player.full_name} team={player.team} size="md" />
                <div className="min-w-0 flex-1">
                  <p className="kicker">{label}</p>
                  <p className="truncate font-semibold">{player.full_name}</p>
                  <p className="truncate text-footnote text-muted-foreground">
                    {[player.team?.abbreviation ?? "No current team", player.position]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setEditing(slot)}
                  className="rounded-full px-3 py-1.5 text-subhead font-medium text-primary hover:bg-muted"
                >
                  Change<span className="sr-only"> {label.toLowerCase()}</span>
                </button>
                <button
                  type="button"
                  onClick={() => remove(slot)}
                  aria-label={`Remove ${player.full_name}`}
                  className={ICON_BUTTON}
                >
                  <X aria-hidden className="size-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-end gap-2">
                <PlayerSearch
                  label={label}
                  onSelect={(p) => choose(slot, p.id)}
                  startOpen={editing === slot}
                  className="min-w-0 flex-1"
                />
                {editing === slot && (
                  <button
                    type="button"
                    onClick={() => setEditing(null)}
                    className="min-h-10 rounded-full px-3 text-subhead font-medium text-muted-foreground hover:text-foreground"
                  >
                    Cancel
                  </button>
                )}
              </div>
            );
          return (
            <div
              key={slot}
              className={cn(
                "relative min-w-0 rounded-xl border border-border bg-card p-3 sm:p-4",
                slot === 1 && "md:order-3",
              )}
            >
              <span
                aria-hidden
                className="absolute inset-x-3 top-0 h-0.5 rounded-full"
                style={{ background: SLOT_COLORS[slot] }}
              />
              {body}
            </div>
          );
        })}
        <div className="flex items-center justify-center md:order-2">
          <button
            type="button"
            onClick={() => go(ids[1], ids[0], true)}
            disabled={!ids[0] || !ids[1]}
            aria-label="Swap players"
            className={cn(ICON_BUTTON, "disabled:pointer-events-none disabled:opacity-40")}
          >
            <ArrowLeftRight aria-hidden className="size-4" />
          </button>
        </div>
      </div>
      <p role="status" className="text-footnote text-negative">
        {duplicate ? "That player is already in the other slot. Pick someone else." : ""}
      </p>
    </div>
  );
}

export function SeasonPicker({
  players,
  seasons,
  season,
}: {
  players: [number, number];
  seasons: string[];
  season: string;
}) {
  const { setSeason, pending } = useCompareNavigation(season);
  return (
    <label className="flex items-center gap-2 text-subhead">
      <span className="text-muted-foreground">Season</span>
      <select
        value={season}
        aria-busy={pending}
        onChange={(e) => setSeason(players[0], players[1], e.target.value)}
        className="min-h-9 rounded-full border border-border bg-card px-3 text-subhead"
      >
        {seasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}

const AXIS = { fontSize: 12, fill: "var(--muted-foreground)" };

/** Both players' season average for one statistic as it built up, aligned by game number. */
export function CompareTrend({ players, season }: { players: [Picked, Picked]; season: string }) {
  const [stat, setStat] = useState<TrendStat>("pts");
  const results = useQueries({
    queries: players.map((p) => ({
      queryKey: ["player-trends", p.id, stat, season],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        clientGet<PlayerTrends>(`/players/${p.id}/trends`, { stat, season }, signal),
      placeholderData: keepPreviousData,
      staleTime: 5 * 60_000,
    })),
  });
  const label = TREND_STATS.find((s) => s.value === stat)!.label;
  const failed = results.find((r) => r.error)?.error;
  const [a, b] = results.map((r) => r.data);
  const length = Math.max(a?.points.length ?? 0, b?.points.length ?? 0);
  const running = (t: PlayerTrends | undefined) => {
    let sum = 0;
    return (t?.points ?? []).map((p, i) => {
      sum += p.value;
      return Math.round((sum / (i + 1)) * 100) / 100;
    });
  };
  const [runA, runB] = [running(a), running(b)];
  const rows = Array.from({ length }, (_, i) => ({
    game: i + 1,
    a: runA[i] ?? null,
    b: runB[i] ?? null,
    aValue: a?.points[i]?.value ?? null,
    bValue: b?.points[i]?.value ?? null,
  }));
  const names = players.map((p) => p.full_name);
  const averages = [a?.average, b?.average];
  const summary =
    a && b
      ? `${season}: ${names[0]} averages ${formatStat(a.average)} and ${names[1]} ${formatStat(b.average)} ${label.toLowerCase()} per game, over ${a.games_played} and ${b.games_played} games.`
      : "Loading both players' games…";

  return (
    <div className="space-y-3">
      <div className="-mx-1 overflow-x-auto px-1">
        <SegmentedControl
          label="Statistic"
          value={stat}
          onChange={setStat}
          segments={TREND_STATS.map((s) => ({ value: s.value, label: s.short }))}
        />
      </div>
      {failed ? (
        <Unavailable kind="error" title="Game-by-game form couldn't load">
          {describeError(failed).message}
        </Unavailable>
      ) : (
        <ChartFrame
          title={`${label}: form through the season`}
          unit={`Season average after each game, by game number in ${season}`}
          summary={summary}
          chart={
            <div aria-busy={results.some((r) => r.isFetching)}>
              <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-footnote text-muted-foreground">
                {names.map((name, i) => (
                  <li key={name} className="flex items-center gap-2">
                    <span
                      aria-hidden
                      className="h-[3px] w-5 rounded-full"
                      style={{ background: SLOT_COLORS[i] }}
                    />
                    {name} · season {formatStat(averages[i])}
                  </li>
                ))}
              </ul>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="game" tick={AXIS} tickLine={false} axisLine={false} minTickGap={16} />
                    <YAxis tick={AXIS} tickLine={false} axisLine={false} width={48} />
                    <Tooltip
                      labelFormatter={(game) => `Game ${game}`}
                      contentStyle={{
                        background: "var(--popover)",
                        border: "1px solid var(--border)",
                        borderRadius: 12,
                        color: "var(--foreground)",
                      }}
                      formatter={(value, name) => [formatStat(Number(value)), String(name)]}
                    />
                    {(["a", "b"] as const).map((key, i) => (
                      <Line
                        key={key}
                        name={names[i]}
                        dataKey={key}
                        stroke={SLOT_COLORS[i]}
                        strokeWidth={2.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          }
          table={
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-subhead tabular-nums">
                <caption className="sr-only">
                  {label} in each game for {names[0]} and {names[1]}, {season}
                </caption>
                <thead className="sticky top-0 bg-card text-footnote text-muted-foreground">
                  <tr className="border-b border-border">
                    <th scope="col" className="py-1.5 text-left font-medium">
                      Game
                    </th>
                    {names.map((n) => (
                      <th key={n} scope="col" className="py-1.5 text-right font-medium">
                        {n}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.game} className="border-b border-border/50 last:border-0">
                      <th scope="row" className="py-1 text-left font-normal">
                        {r.game}
                      </th>
                      <td className="py-1 text-right">{formatGameValue(r.aValue)}</td>
                      <td className="py-1 text-right">{formatGameValue(r.bValue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
        />
      )}
      <p className="text-footnote text-muted-foreground">
        Full scouting reports:{" "}
        {players.map((p, i) => (
          <span key={p.id}>
            {i > 0 && " · "}
            <Link
              href={`/players/${p.id}?season=${season}`}
              className="font-medium text-primary hover:underline"
            >
              {p.full_name}
            </Link>
          </span>
        ))}
      </p>
    </div>
  );
}
