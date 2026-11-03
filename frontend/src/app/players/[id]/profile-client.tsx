"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useOptimistic, useState, useTransition } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame } from "@/components/data/chart-frame";
import { type Column, DataTable } from "@/components/data/data-table";
import { SegmentedControl } from "@/components/data/segmented-control";
import { TeamMark } from "@/components/brand/team-mark";
import type {
  CareerLine,
  CareerSeason,
  PlayerCareer,
  PlayerGameLine,
  Split,
  TrendPoint,
} from "@/lib/api/types";
import { formatGameDate, formatGameValue, formatPercent, formatStat } from "@/lib/format";

import { TREND_STATS, TREND_VIEWS, type TrendStat, type TrendView } from "./stats";

export function ProfileControls({
  seasons,
  season,
  stat,
}: {
  seasons: string[];
  season: string;
  stat: TrendStat;
}) {
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
      {seasons.length > 0 && (
        <div>
          <label htmlFor={`${id}-season`} className="kicker mb-1.5 block">
            Season
          </label>
          <select
            id={`${id}-season`}
            value={shown.season}
            onChange={(event) => update("season", event.target.value)}
            className="field"
          >
            {seasons.map((label) => (
              <option key={label} value={label}>
                {label}
              </option>
            ))}
          </select>
        </div>
      )}

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

/** Switches the chart between this season, each year of the career and the running career total. */
export function TrendViewControl({ view, hasSeason = true }: { view: TrendView; hasSeason?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [shown, setShown] = useOptimistic(view);
  const [, startTransition] = useTransition();
  return (
    <SegmentedControl
      label="Time span"
      value={shown}
      segments={TREND_VIEWS.filter((v) => hasSeason || v.value !== "season").map((v) => ({
        value: v.value,
        label: v.label,
      }))}
      onChange={(value) => {
        const params = new URLSearchParams(searchParams.toString());
        if (value === "season") params.delete("view");
        else params.set("view", value);
        const query = params.toString();
        startTransition(() => {
          setShown(value);
          router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
        });
      }}
    />
  );
}

const WHOLE = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** Regular-season career by year (per-game averages) or all time (running total), oldest first. */
export function CareerTrend({
  career,
  name,
  stat,
  view,
  hasSeason,
}: {
  career: PlayerCareer;
  name: string;
  stat: TrendStat;
  view: "years" | "all";
  hasSeason: boolean;
}) {
  const label = TREND_STATS.find((s) => s.value === stat)!.label;
  const { seasons, totals, partial } = career.regular;
  const recorded = seasons.flatMap((s) => {
    const average = s.per_game[stat];
    return average == null
      ? []
      : [{ season: s.season, games: s.games, average, total: Math.round(average * s.games) }];
  });
  const rows = recorded.map((r, i) => ({
    ...r,
    running: recorded.slice(0, i + 1).reduce((sum, x) => sum + x.total, 0),
  }));
  const running = rows.at(-1)?.running ?? 0;
  const control = <TrendViewControl view={view} hasSeason={hasSeason} />;
  if (rows.length === 0) {
    return (
      <ChartFrame
        title={`${label} by year`}
        unit="Regular season"
        summary={`No ${label.toLowerCase()} are on record for ${name}.`}
        actions={control}
        chart={null}
        table={null}
      />
    );
  }
  const best = rows.reduce((top, r) => (r.average > top.average ? r : top), rows[0]);
  const games = rows.reduce((sum, r) => sum + r.games, 0);
  const span = `${rows[0].season} to ${rows.at(-1)!.season}`;
  const careerAverage = totals?.per_game[stat] ?? null;
  const years = view === "years";
  const dataKey = years ? "average" : "running";
  const color = years ? "var(--chart-3)" : "var(--chart-1)";
  const since = partial[stat] ? ` ${label} weren't tracked until ${partial[stat]}.` : "";
  const summary =
    (years
      ? `${name} averaged ${formatStat(careerAverage)} ${label.toLowerCase()} per game over ${rows.length} ${rows.length === 1 ? "season" : "seasons"}, ${span}. Best year: ${formatStat(best.average)} in ${best.season}.`
      : `${name} has ${WHOLE.format(running)} career ${label.toLowerCase()} in ${WHOLE.format(games)} regular-season games, ${span}.`) +
    since;
  return (
    <ChartFrame
      title={years ? `${label} by year` : `${label}, all time`}
      unit={
        years
          ? `${label} per game each regular season`
          : `Running career total at the end of each regular season`
      }
      summary={summary}
      actions={control}
      chart={
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="season" tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
              <YAxis
                tick={AXIS}
                tickLine={false}
                axisLine={false}
                width={60}
                tickFormatter={(v) => WHOLE.format(Number(v))}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--foreground)",
                }}
                formatter={(value) => [
                  years ? formatStat(Number(value)) : WHOLE.format(Number(value)),
                  years ? `${label} per game` : `Career ${label.toLowerCase()}`,
                ]}
              />
              {years && careerAverage != null && (
                <ReferenceLine
                  y={careerAverage}
                  stroke="var(--chart-2)"
                  strokeDasharray="4 3"
                  label={{
                    value: `Career ${formatStat(careerAverage)}`,
                    position: "insideTopRight",
                    fill: "var(--chart-2)",
                    fontSize: 12,
                  }}
                />
              )}
              <Line dataKey={dataKey} stroke={color} strokeWidth={2.5} dot={{ r: 3, fill: color }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      }
      table={
        <DataTable
          caption={`${name}, ${label.toLowerCase()} by regular season`}
          rows={[...rows].reverse()}
          rowKey={(r) => r.season}
          columns={[
            { key: "season", header: "Season", cell: (r) => r.season, sortValue: (r) => r.season },
            {
              key: "games",
              header: "GP",
              description: "Games played",
              numeric: true,
              cell: (r) => r.games,
              sortValue: (r) => r.games,
            },
            {
              key: "average",
              header: "Per game",
              numeric: true,
              cell: (r) => formatStat(r.average),
              sortValue: (r) => r.average,
            },
            {
              key: "total",
              header: "Season total",
              numeric: true,
              cell: (r) => WHOLE.format(r.total),
              sortValue: (r) => r.total,
            },
            {
              key: "running",
              header: "Career total",
              numeric: true,
              cell: (r) => WHOLE.format(r.running),
              sortValue: (r) => r.running,
            },
          ]}
        />
      }
    />
  );
}

function LegendSwatch({
  color,
  width,
  dash,
  dot,
}: {
  color: string;
  width: number;
  dash?: string;
  dot?: boolean;
}) {
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
            <Line
              name="Previous 5 average"
              dataKey="rolling_5"
              stroke="var(--chart-1)"
              strokeWidth={3}
              dot={false}
            />
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
  {
    key: "value",
    header: "Value",
    cell: (p) => formatGameValue(p.value),
    sortValue: (p) => p.value,
    numeric: true,
  },
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
  return (
    <DataTable
      caption={caption}
      columns={TREND_COLUMNS}
      rows={[...points].reverse()}
      rowKey={(p) => p.game_id}
    />
  );
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
  {
    key: "pm",
    header: "+/−",
    description: "Plus-minus",
    cell: (g) => signed(g.box.plus_minus),
    numeric: true,
  },
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
  {
    key: "gp",
    header: "GP",
    description: "Games played",
    cell: (s) => s.summary.games_played,
    numeric: true,
  },
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

type CareerRow = CareerLine & Partial<Pick<CareerSeason, "season" | "age" | "teams">>;

const PER_GAME_COLUMNS = [
  { key: "min", header: "MIN", description: "Minutes per game" },
  { key: "pts", header: "PTS", description: "Points per game" },
  { key: "reb", header: "REB", description: "Rebounds per game" },
  { key: "ast", header: "AST", description: "Assists per game" },
  { key: "stl", header: "STL", description: "Steals per game" },
  { key: "blk", header: "BLK", description: "Blocks per game" },
  { key: "fg3m", header: "3PM", description: "3-pointers made per game" },
] as const;

const CAREER_COLUMNS: Column<CareerRow>[] = [
  {
    key: "season",
    header: "Season",
    cell: (r) => r.season ?? "Career",
    sortValue: (r) => r.season ?? null,
  },
  {
    key: "team",
    header: "Team",
    cell: (r) =>
      r.teams ? (
        <span className="flex items-center gap-1.5">
          {r.teams.map((t) =>
            t.team ? (
              <span
                key={t.abbreviation}
                className="inline-flex items-center gap-1"
                title={`${t.team.city} ${t.team.name}`}
              >
                <TeamMark team={t.team} size="xs" />
                <span>{t.abbreviation}</span>
              </span>
            ) : (
              <span key={t.abbreviation} title="Franchise no longer in the league">
                {t.abbreviation}
              </span>
            ),
          )}
        </span>
      ) : null,
  },
  { key: "age", header: "Age", numeric: true, cell: (r) => r.age ?? "", sortValue: (r) => r.age ?? null },
  {
    key: "gp",
    header: "GP",
    description: "Games played",
    numeric: true,
    cell: (r) => r.games,
    sortValue: (r) => r.games,
  },
  ...PER_GAME_COLUMNS.map((c) => ({
    ...c,
    numeric: true,
    cell: (r: CareerRow) => formatStat(r.per_game[c.key]),
    sortValue: (r: CareerRow) => r.per_game[c.key] ?? null,
  })),
  {
    key: "fg",
    header: "FG%",
    description: "Field goal percentage",
    numeric: true,
    cell: (r) => formatPercent(r.fg_pct),
    sortValue: (r) => r.fg_pct,
  },
  {
    key: "fg3",
    header: "3P%",
    description: "3-point percentage",
    numeric: true,
    cell: (r) => formatPercent(r.fg3_pct),
    sortValue: (r) => r.fg3_pct,
  },
  {
    key: "ft",
    header: "FT%",
    description: "Free throw percentage",
    numeric: true,
    cell: (r) => formatPercent(r.ft_pct),
    sortValue: (r) => r.ft_pct,
  },
];

const PARTIAL_NAMES: Record<string, string> = {
  stl: "Steals",
  blk: "Blocks",
  fg3m: "3-pointers",
  tov: "Turnovers",
  min: "Minutes",
  reb: "Rebounds",
  ast: "Assists",
};

/** Every season of a career, regular season or playoffs, with career averages underneath. */
export function CareerHistory({ career, name }: { career: PlayerCareer; name: string }) {
  const [kind, setKind] = useState<"regular" | "playoffs">("regular");
  const table = career[kind];
  const label = kind === "regular" ? "regular season" : "playoffs";
  const notes = Object.entries(table.partial)
    .filter(([key]) => PER_GAME_COLUMNS.some((c) => c.key === key))
    .map(
      ([key, since]) =>
        `${PARTIAL_NAMES[key] ?? key} weren't tracked until ${since}, so the career average counts from then.`,
    );
  const best = table.seasons.reduce<CareerSeason | null>(
    (top, s) => ((s.per_game.pts ?? -1) > (top?.per_game.pts ?? -1) ? s : top),
    null,
  );
  return (
    <section aria-labelledby="career-heading" className="rule-top space-y-4 pt-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="career-heading" className="headline text-[1.875rem]">
            Career
          </h2>
          <p className="text-footnote text-muted-foreground">
            {table.seasons.length > 0
              ? `${table.seasons.length} ${table.seasons.length === 1 ? "season" : "seasons"}, ${table.seasons[0].season} to ${table.seasons.at(-1)!.season} · per game`
              : `No ${label} games`}
            {best?.per_game.pts != null &&
              ` · best scoring season ${best.season} (${formatStat(best.per_game.pts)} points)`}
          </p>
        </div>
        {career.playoffs.seasons.length > 0 && (
          <SegmentedControl
            label="Season type"
            segments={[
              { value: "regular", label: "Regular season" },
              { value: "playoffs", label: "Playoffs" },
            ]}
            value={kind}
            onChange={setKind}
          />
        )}
      </div>
      {table.seasons.length > 0 && (
        <DataTable<CareerRow>
          key={kind}
          caption={`${name}, career ${label} averages by season`}
          columns={CAREER_COLUMNS}
          rows={table.seasons}
          rowKey={(r) => r.season ?? "career"}
          footer={table.totals ?? undefined}
        />
      )}
      {notes.length > 0 && (
        <ul className="space-y-1 text-footnote text-muted-foreground">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
