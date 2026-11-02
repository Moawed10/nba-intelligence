"use client";

import { useState } from "react";

import { SegmentedControl } from "@/components/data/segmented-control";
import type { PlayerGameLine, PredictedValue } from "@/lib/api/types";
import { formatStat } from "@/lib/format";

const STATS = [
  { value: "pts", label: "Points", unit: "points" },
  { value: "reb", label: "Rebounds", unit: "rebounds" },
  { value: "ast", label: "Assists", unit: "assists" },
] as const;
type Stat = (typeof STATS)[number]["value"];

const WIDTH = 640;
const HEIGHT = 150;
const PAD = { left: 16, right: 16, top: 26, bottom: 30 };
const DOT = 5;

function niceStep(max: number): number {
  return max <= 12 ? 2 : max <= 25 ? 5 : 10;
}

/**
 * The forecast against the player's real recent games: each dot is one game, the shaded band is
 * the 80% range and the line is the forecast. Nothing here is simulated.
 */
export function RecentRange({
  games,
  values,
  firstName,
}: {
  games: PlayerGameLine[];
  values: Partial<Record<string, PredictedValue>>;
  firstName: string;
}) {
  const [stat, setStat] = useState<Stat>("pts");
  const forecast = values[stat];
  if (!forecast || games.length === 0) return null;
  const { unit } = STATS.find((s) => s.value === stat)!;
  const results = games.map((g) => g.box[stat]);
  const top = Math.max(...results, forecast.upper);
  const step = niceStep(top);
  const max = Math.ceil((top + 1) / step) * step;
  const x = (v: number) => PAD.left + (v / max) * (WIDTH - PAD.left - PAD.right);
  const base = HEIGHT - PAD.bottom - DOT;
  const stacks = new Map<number, number>();
  const dots = results.map((v, i) => {
    const level = stacks.get(v) ?? 0;
    stacks.set(v, level + 1);
    return { v, i, cy: base - level * (DOT * 2 + 1) };
  });
  const within = (v: number) => v >= forecast.lower && v <= forecast.upper;
  const lower = Math.round(forecast.lower);
  const upper = Math.round(forecast.upper);
  const inside = results.filter(within).length;
  const summary = `${firstName} finished between ${lower} and ${upper} ${unit}, the range expected for this game, in ${inside} of the last ${results.length} games.`;
  const ticks = Array.from({ length: max / step + 1 }, (_, i) => i * step);

  return (
    <section aria-labelledby="recent-range-heading" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="recent-range-heading" className="kicker">
          This forecast vs. the last {results.length} games
        </h3>
        <SegmentedControl label="Statistic" segments={[...STATS]} value={stat} onChange={setStat} />
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Dot chart of ${unit} in each of the last ${results.length} games, with the forecast of ${formatStat(forecast.point)} and the expected range of ${lower} to ${upper}.`}
        className="w-full"
      >
        <rect
          x={x(forecast.lower)}
          y={PAD.top - 8}
          width={Math.max(2, x(forecast.upper) - x(forecast.lower))}
          height={base + DOT - PAD.top + 8}
          rx={6}
          className="fill-primary/15"
        />
        <line
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={base + DOT + 2}
          y2={base + DOT + 2}
          className="stroke-border"
        />
        {ticks.map((t) => (
          <text
            key={t}
            x={x(t)}
            y={HEIGHT - 10}
            textAnchor="middle"
            className="fill-muted-foreground text-[12px] tabular-nums"
          >
            {t}
          </text>
        ))}
        {dots.map((d) => (
          <circle
            key={d.i}
            cx={x(d.v)}
            cy={d.cy}
            r={DOT}
            className={within(d.v) ? "fill-primary" : "fill-muted-foreground/60"}
          />
        ))}
        <line
          x1={x(forecast.point)}
          x2={x(forecast.point)}
          y1={PAD.top - 8}
          y2={base + DOT}
          strokeWidth={2.5}
          className="stroke-foreground"
        />
        <text
          x={x(forecast.point)}
          y={PAD.top - 12}
          textAnchor="middle"
          className="fill-foreground text-[13px] font-semibold tabular-nums"
        >
          Forecast {formatStat(forecast.point)}
        </text>
      </svg>
      <p className="text-subhead">{summary}</p>
      <p className="text-footnote text-muted-foreground">
        Each dot is a real game. Highlighted dots fell inside the shaded range, which should hold about 4
        games in 5.
      </p>
    </section>
  );
}
