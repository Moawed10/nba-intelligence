"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { TeamMark } from "@/components/brand/team-mark";
import { ChartFrame } from "@/components/data/chart-frame";
import { type Column, DataTable } from "@/components/data/data-table";
import { PlayerSearch } from "@/components/data/player-search";
import { SegmentedControl } from "@/components/data/segmented-control";
import { Unavailable } from "@/components/data/unavailable";
import { clientGet } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import type { HistoryEntry, ModelAnalytics, PlayerSearchResult, PredictionHistory } from "@/lib/api/types";
import { formatGameDate, formatPercent, formatStat } from "@/lib/format";
import { TARGET_ORDER, targetLabel } from "@/lib/models";

type Kind = "backtest" | "pregame";
const SHORT: Record<string, string> = {
  pts: "PTS",
  reb: "REB",
  ast: "AST",
  fg3m: "3PM",
  stl: "STL",
  blk: "BLK",
  min: "MIN",
};
type Stat = (typeof TARGET_ORDER)[number];

const AXIS = { fontSize: 12, fill: "var(--muted-foreground)" };
const TOOLTIP = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 12,
  color: "var(--foreground)",
};
const KINDS = (testSeason: string) => [
  { value: "backtest" as const, label: `${testSeason} test` },
  { value: "pregame" as const, label: "Live" },
];
const KIND_NOTE: Record<Kind, string> = {
  backtest:
    "Backtest: made after the fact by the release's held-out models, which never saw this season, then scored against the box scores.",
  pregame: "Pregame: stored before tip-off and scored once the game was final.",
};

function minutesLabel(from: number | null, to: number | null): string {
  if (from == null && to != null) return `Under ${Math.round(to)} min`;
  if (to == null && from != null) return `${Math.round(from)}+ min`;
  return `${Math.round(from ?? 0)}–${Math.round(to ?? 0)} min`;
}

function Charts({ data, unit }: { data: ModelAnalytics; unit: string }) {
  const calibration = data.calibration.map((p) => ({ ...p, predicted: Number(p.predicted.toFixed(1)) }));
  const residuals = data.residuals.map((b) => ({
    ...b,
    label: formatStat((b.lower + b.upper) / 2),
    share: (b.n / data.n) * 100,
  }));
  const coverage = data.coverage_by_bin.map((b) => ({
    label: minutesLabel(b.minutes_from, b.minutes_to),
    coverage: b.coverage == null ? null : b.coverage * 100,
    n: b.n,
  }));
  const worst = data.calibration.reduce((w, p) => Math.max(w, Math.abs(p.actual - p.predicted)), 0);
  const reach = (data.mae ?? 0) * 2;
  const within = data.residuals
    .filter((b) => b.lower >= -reach && b.upper <= reach)
    .reduce((s, b) => s + b.n, 0);
  const lowest = coverage.reduce<number | null>(
    (low, b) => (b.coverage != null && (low == null || b.coverage < low) ? b.coverage : low),
    null,
  );

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <ChartFrame
        title="Predicted vs. actual"
        unit={`Average ${unit} per tenth of predictions`}
        summary={`Sorted from lowest to highest prediction and split into tenths, the actual average was never more than ${formatStat(worst)} ${unit} from what was predicted.`}
        chart={
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={calibration} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="predicted"
                  type="number"
                  tick={AXIS}
                  tickLine={false}
                  axisLine={false}
                  domain={["dataMin", "dataMax"]}
                />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} width={48} />
                <Tooltip
                  contentStyle={TOOLTIP}
                  formatter={(v, name) => [formatStat(Number(v)), String(name)]}
                  labelFormatter={(v) => `Predicted ${formatStat(Number(v))}`}
                />
                <Line
                  name="Perfect match"
                  dataKey="predicted"
                  stroke="var(--muted-foreground)"
                  strokeDasharray="4 4"
                  dot={false}
                />
                <Line
                  name="Actual average"
                  dataKey="actual"
                  stroke="var(--chart-1)"
                  strokeWidth={3}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        }
        table={
          <DataTable
            caption="Predicted vs. actual by tenth of predictions"
            rowKey={(r) => String(r.predicted)}
            rows={data.calibration}
            columns={[
              { key: "p", header: "Predicted", numeric: true, cell: (r) => formatStat(r.predicted) },
              { key: "a", header: "Actual", numeric: true, cell: (r) => formatStat(r.actual) },
              { key: "n", header: "Games", numeric: true, cell: (r) => r.n.toLocaleString("en-US") },
            ]}
          />
        }
      />
      <ChartFrame
        title="How far off"
        unit={`Share of games by miss (actual minus predicted, ${unit})`}
        summary={`${formatPercent(within / data.n)} of predictions were within ${formatStat(reach)} ${unit} of the result. On average they ran ${(data.bias ?? 0) > 0 ? "low" : "high"} by ${formatStat(Math.abs(data.bias ?? 0))}.`}
        chart={
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={residuals} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} minTickGap={16} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} width={48} unit="%" />
                <Tooltip
                  contentStyle={TOOLTIP}
                  formatter={(v) => [`${formatStat(Number(v))}%`, "Games"]}
                  labelFormatter={(v) => `Off by about ${v}`}
                />
                <Bar dataKey="share" fill="var(--chart-2)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        }
        table={
          <DataTable
            caption="Games by miss"
            rowKey={(r) => String(r.lower)}
            rows={data.residuals}
            columns={[
              {
                key: "r",
                header: "Miss",
                cell: (r) => `${formatStat(r.lower)} to ${formatStat(r.upper)}`,
              },
              { key: "n", header: "Games", numeric: true, cell: (r) => r.n.toLocaleString("en-US") },
            ]}
          />
        }
      />
      <ChartFrame
        title="Range hit rate"
        unit="Share of results inside the 80% range, by expected minutes"
        summary={
          lowest != null
            ? `The range held ${formatPercent(data.coverage)} of the time overall and at least ${formatPercent(lowest / 100)} in every group (target 80%).`
            : "No range results yet."
        }
        chart={
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={coverage} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} width={48} unit="%" domain={[0, 100]} />
                <ReferenceLine y={80} stroke="var(--primary)" strokeDasharray="4 4" />
                <Tooltip
                  contentStyle={TOOLTIP}
                  formatter={(v) => [`${formatStat(Number(v))}%`, "Inside range"]}
                />
                <Bar dataKey="coverage" fill="var(--chart-1)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        }
        table={
          <DataTable
            caption="Range hit rate by expected minutes"
            rowKey={(r) => r.label}
            rows={coverage}
            columns={[
              { key: "m", header: "Expected minutes", cell: (r) => r.label },
              {
                key: "c",
                header: "Inside range",
                numeric: true,
                cell: (r) => (r.coverage == null ? "—" : `${formatStat(r.coverage)}%`),
              },
              { key: "n", header: "Games", numeric: true, cell: (r) => r.n.toLocaleString("en-US") },
            ]}
          />
        }
      />
    </div>
  );
}

/** Stored, scored predictions for one statistic: how close they were and how often the range held. */
export function PredictionCheck({
  version,
  testSeason,
  initial,
}: {
  version: string;
  testSeason: string;
  initial: ModelAnalytics | null;
}) {
  const [stat, setStat] = useState<Stat>("pts");
  const [kind, setKind] = useState<Kind>("backtest");
  const query = useQuery({
    queryKey: ["model-analytics", version, stat, kind],
    queryFn: ({ signal }) =>
      clientGet<ModelAnalytics>(`/models/${version}/analytics`, { stat, kind }, signal),
    initialData: stat === "pts" && kind === "backtest" && initial ? initial : undefined,
    staleTime: 5 * 60_000,
  });
  const data = query.data;
  const unit = targetLabel(stat).toLowerCase();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl label="Predictions" segments={KINDS(testSeason)} value={kind} onChange={setKind} />
        <SegmentedControl
          label="Statistic"
          segments={TARGET_ORDER.map((t) => ({ value: t, label: SHORT[t] }))}
          className="max-w-full overflow-x-auto"
          value={stat}
          onChange={setStat}
        />
      </div>
      <p className="text-footnote text-muted-foreground">{KIND_NOTE[kind]}</p>
      {query.error ? (
        <Unavailable kind="error" title="These results couldn't load">
          {describeError(query.error).message}
        </Unavailable>
      ) : !data ? (
        <div aria-busy className="h-72 animate-pulse rounded-xl bg-muted/40">
          <span className="sr-only">Loading results</span>
        </div>
      ) : data.n === 0 ? (
        <Unavailable
          kind="empty"
          title={
            kind === "pregame" ? "No live predictions scored yet" : "No backtest stored for this release"
          }
        >
          {kind === "pregame"
            ? "Live forecasts are scored once their games are final. Results appear here as the season goes on."
            : "Backtests are created offline for each release; this one has none yet."}
        </Unavailable>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              [
                "Games checked",
                data.n.toLocaleString("en-US"),
                `${formatGameDate(data.first_game!, true)} – ${formatGameDate(data.last_game!, true)}`,
              ],
              ["Average miss", formatStat(data.mae), unit],
              ["Typical big miss", formatStat(data.rmse), "root mean squared error"],
              ["Inside the range", formatPercent(data.coverage), "target 80%"],
            ].map(([term, value, note]) => (
              <div key={term} className="rounded-xl bg-muted/40 px-4 py-3">
                <dt className="text-footnote text-muted-foreground">{term}</dt>
                <dd className="numeral text-title2">{value}</dd>
                <dd className="text-footnote text-muted-foreground">{note}</dd>
              </div>
            ))}
          </dl>
          <Charts data={data} unit={unit} />
        </>
      )}
    </div>
  );
}

const HISTORY_STATS = ["pts", "reb", "ast"] as const;

const HISTORY_COLUMNS: Column<HistoryEntry>[] = [
  {
    key: "date",
    header: "Date",
    cell: (e) => formatGameDate(e.game_date, true),
    sortValue: (e) => e.game_date,
  },
  {
    key: "opp",
    header: "Opponent",
    cell: (e) => (
      <span className="flex items-center gap-2">
        <TeamMark team={e.opponent} size="xs" />
        {e.is_home ? "vs" : "@"} {e.opponent.abbreviation}
      </span>
    ),
  },
  ...HISTORY_STATS.flatMap((stat): Column<HistoryEntry>[] => [
    {
      key: `${stat}-p`,
      header: `${targetLabel(stat)} predicted`,
      numeric: true,
      cell: (e) => {
        const v = e.values[stat];
        return v ? (
          <span>
            {formatStat(v.point)}{" "}
            <span className="text-muted-foreground">
              ({Math.round(v.lower)}–{Math.round(v.upper)})
            </span>
          </span>
        ) : (
          "—"
        );
      },
    },
    {
      key: `${stat}-a`,
      header: "Actual",
      numeric: true,
      cell: (e) => {
        const v = e.values[stat];
        if (!v || v.actual == null) return <span className="text-muted-foreground">Not played yet</span>;
        return (
          <span className={v.within_interval ? "font-semibold" : "text-muted-foreground"}>
            {v.actual}
            <span className="sr-only">
              {v.within_interval ? ", inside the range" : ", outside the range"}
            </span>
            <span aria-hidden className="text-primary">
              {v.within_interval ? " ✓" : ""}
            </span>
          </span>
        );
      },
      sortValue: (e) => e.values[stat]?.actual ?? null,
    },
  ]),
];

/** Any player's stored predictions next to what happened, backtest or pregame. */
export function PredictionHistoryExplorer({ testSeason }: { testSeason: string }) {
  const [player, setPlayer] = useState<PlayerSearchResult | null>(null);
  const [kind, setKind] = useState<Kind>("backtest");
  const query = useQuery({
    queryKey: ["prediction-history", player?.id, kind],
    queryFn: ({ signal }) =>
      clientGet<PredictionHistory>(
        "/predictions/history",
        { player_id: player!.id, kind, limit: 30 },
        signal,
      ),
    enabled: player != null,
    staleTime: 5 * 60_000,
  });
  const entries = query.data?.entries ?? [];
  const scored = entries.filter((e) => e.values.pts?.actual != null);
  const inside = scored.filter((e) => e.values.pts?.within_interval).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <PlayerSearch label="Player" onSelect={setPlayer} className="min-w-64 flex-1" />
        <SegmentedControl label="Predictions" segments={KINDS(testSeason)} value={kind} onChange={setKind} />
      </div>
      <p className="text-footnote text-muted-foreground">{KIND_NOTE[kind]}</p>
      {!player ? (
        <Unavailable kind="empty" title="Pick a player">
          Search for any player to see each stored prediction next to the box score.
        </Unavailable>
      ) : query.error ? (
        <Unavailable kind="error" title="This history couldn't load">
          {describeError(query.error).message}
        </Unavailable>
      ) : query.isPending ? (
        <div aria-busy className="h-48 animate-pulse rounded-xl bg-muted/40">
          <span className="sr-only">Loading predictions</span>
        </div>
      ) : entries.length === 0 ? (
        <Unavailable
          kind="empty"
          title={`No ${kind === "backtest" ? "backtest" : "pregame"} predictions for ${player.full_name}`}
        >
          {kind === "backtest"
            ? `Backtests cover players with enough games in ${testSeason}.`
            : "Live forecasts are stored when someone opens a forecast before tip-off."}
        </Unavailable>
      ) : (
        <>
          <p className="text-subhead">
            {scored.length
              ? `Points landed inside the predicted range in ${inside} of the ${scored.length} scored games shown for ${player.full_name}.`
              : `None of these ${entries.length} games has been played yet.`}
          </p>
          <DataTable
            key={`${player.id}-${kind}`}
            caption={`${player.full_name}, ${kind} predictions and results`}
            columns={HISTORY_COLUMNS}
            rows={entries}
            rowKey={(e) => e.prediction_id}
          />
        </>
      )}
    </div>
  );
}
