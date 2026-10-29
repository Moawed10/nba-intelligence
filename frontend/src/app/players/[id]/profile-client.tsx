"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useOptimistic, useTransition } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { type Column, DataTable } from "@/components/data/data-table";
import { SegmentedControl } from "@/components/data/segmented-control";
import type { PlayerGameLine, Split, TrendPoint } from "@/lib/api/types";
import { formatGameDate, formatGameValue, formatPercent, formatStat } from "@/lib/format";

import { TREND_STATS, type TrendStat } from "./stats";

export function ProfileControls({ seasons, season, stat }: { seasons: string[]; season: string; stat: TrendStat }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [shown, setShown] = useOptimistic({ season, stat });
  const id = useId();

  function update(key: "season" | "stat", value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, value);
    if (key === "season") params.delete("log");
    startTransition(() => {
      setShown({ ...shown, [key]: value });
      router.replace(`${pathname}?${params}`, { scroll: false });
    });
  }

  return (
    <div aria-busy={pending} className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <label htmlFor={`${id}-season`} className="mb-1.5 block text-subhead font-medium">
          Season
        </label>
        <select
          id={`${id}-season`}
          value={shown.season}
          onChange={(event) => update("season", event.target.value)}
          className="h-11 rounded-xl border border-input bg-card px-3 text-body outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {seasons.map((label) => (
            <option key={label} value={label}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <SegmentedControl
          label="Trend statistic"
          value={shown.stat}
          onChange={(value) => update("stat", value)}
          segments={TREND_STATS.map((s) => ({ value: s.value, label: s.short }))}
        />
      </div>
      <p role="status" className="sr-only">
        {pending ? "Updating…" : ""}
      </p>
    </div>
  );
}

const AXIS = { fontSize: 12, fill: "var(--muted-foreground)" };

function LegendSwatch({ color, width, dash, dot }: { color: string; width: number; dash?: string; dot?: boolean }) {
  return (
    <svg aria-hidden width="20" height="8">
      <line x1="0" y1="4" x2="20" y2="4" stroke={color} strokeWidth={width} strokeDasharray={dash} />
      {dot && <circle cx="10" cy="4" r="3" fill={color} />}
    </svg>
  );
}

export function TrendChart({ points, statLabel }: { points: TrendPoint[]; statLabel: string }) {
  const data = points.map((p) => ({ ...p, date: formatGameDate(p.game_date) }));
  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-footnote text-muted-foreground">
        <li className="flex items-center gap-2">
          <LegendSwatch color="var(--chart-3)" width={1.5} dot />
          Each game
        </li>
        <li className="flex items-center gap-2">
          <LegendSwatch color="var(--chart-1)" width={3} />
          Average of previous 5 games
        </li>
        <li className="flex items-center gap-2">
          <LegendSwatch color="var(--chart-2)" width={2} dash="4 3" />
          Average of previous 10 games
        </li>
      </ul>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={48} />
            <Tooltip
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                color: "var(--foreground)",
              }}
              formatter={(value, name) => [formatGameValue(Number(value)), String(name)]}
            />
            <Line
              name={statLabel}
              dataKey="value"
              stroke="var(--chart-3)"
              strokeWidth={1.5}
              dot={{ r: 2.5, fill: "var(--chart-3)" }}
            />
            <Line name="Previous 5 average" dataKey="rolling_5" stroke="var(--chart-1)" strokeWidth={3} dot={false} />
            <Line
              name="Previous 10 average"
              dataKey="rolling_10"
              stroke="var(--chart-2)"
              strokeWidth={2}
              strokeDasharray="4 3"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const TREND_COLUMNS: Column<TrendPoint>[] = [
  { key: "date", header: "Date", cell: (p) => formatGameDate(p.game_date), sortValue: (p) => p.game_date },
  { key: "opp", header: "Opponent", cell: (p) => `${p.is_home ? "vs" : "@"} ${p.opponent_abbreviation}` },
  { key: "value", header: "Value", cell: (p) => formatGameValue(p.value), sortValue: (p) => p.value, numeric: true },
  {
    key: "r5",
    header: "Prev 5",
    description: "Average of the previous 5 games",
    cell: (p) => formatStat(p.rolling_5),
    numeric: true,
  },
  {
    key: "r10",
    header: "Prev 10",
    description: "Average of the previous 10 games",
    cell: (p) => formatStat(p.rolling_10),
    numeric: true,
  },
];

export function TrendTable({ points, caption }: { points: TrendPoint[]; caption: string }) {
  return <DataTable caption={caption} columns={TREND_COLUMNS} rows={[...points].reverse()} rowKey={(p) => p.game_id} />;
}

function result(game: PlayerGameLine): string {
  if (game.result == null || game.team_score == null) return "—";
  return `${game.result} ${game.team_score}–${game.opponent_score}`;
}

function signed(value: number | null): string {
  if (value == null) return "—";
  return value > 0 ? `+${value}` : String(value);
}

const GAME_COLUMNS: Column<PlayerGameLine>[] = [
  { key: "date", header: "Date", cell: (g) => formatGameDate(g.game_date, true) },
  {
    key: "opp",
    header: "Opp",
    description: "Opponent",
    cell: (g) => `${g.is_home ? "vs" : "@"} ${g.opponent.abbreviation}`,
  },
  { key: "result", header: "Result", cell: result },
  { key: "min", header: "MIN", description: "Minutes", cell: (g) => formatStat(g.minutes), numeric: true },
  { key: "pts", header: "PTS", description: "Points", cell: (g) => g.box.pts, numeric: true },
  { key: "reb", header: "REB", description: "Rebounds", cell: (g) => g.box.reb, numeric: true },
  { key: "ast", header: "AST", description: "Assists", cell: (g) => g.box.ast, numeric: true },
  { key: "fg3m", header: "3PM", description: "3-pointers made", cell: (g) => g.box.fg3m, numeric: true },
  { key: "stl", header: "STL", description: "Steals", cell: (g) => g.box.stl, numeric: true },
  { key: "blk", header: "BLK", description: "Blocks", cell: (g) => g.box.blk, numeric: true },
  {
    key: "fg",
    header: "FG",
    description: "Field goals made–attempted",
    cell: (g) => `${g.box.fgm}–${g.box.fga}`,
    numeric: true,
  },
  { key: "tov", header: "TOV", description: "Turnovers", cell: (g) => g.box.tov, numeric: true },
  { key: "pm", header: "+/−", description: "Plus-minus", cell: (g) => signed(g.box.plus_minus), numeric: true },
];

export function GameLogTable({ games, caption }: { games: PlayerGameLine[]; caption: string }) {
  return <DataTable caption={caption} columns={GAME_COLUMNS} rows={games} rowKey={(g) => g.game_id} />;
}

const perGame = (key: "pts" | "reb" | "ast" | "min", description: string): Column<Split> => ({
  key,
  header: key.toUpperCase(),
  description,
  cell: (s) => formatStat(s.summary.per_game[key]),
  numeric: true,
});

const SPLIT_COLUMNS: Column<Split>[] = [
  { key: "split", header: "Split", cell: (s) => s.label },
  { key: "gp", header: "GP", description: "Games played", cell: (s) => s.summary.games_played, numeric: true },
  perGame("pts", "Points per game"),
  perGame("reb", "Rebounds per game"),
  perGame("ast", "Assists per game"),
  perGame("min", "Minutes per game"),
  {
    key: "fg",
    header: "FG%",
    description: "Field goal percentage",
    cell: (s) => formatPercent(s.summary.shooting.fg_pct),
    numeric: true,
  },
  {
    key: "fg3",
    header: "3P%",
    description: "Three-point percentage",
    cell: (s) => formatPercent(s.summary.shooting.fg3_pct),
    numeric: true,
  },
];

export function SplitsTable({ splits, caption }: { splits: Split[]; caption: string }) {
  return <DataTable caption={caption} columns={SPLIT_COLUMNS} rows={splits} rowKey={(s) => s.key} />;
}
