"use client";

import { useState, useTransition } from "react";

import { IntervalBar } from "@/components/data/interval-bar";
import { Unavailable, kindForError } from "@/components/data/unavailable";
import { clientPost } from "@/lib/api/client";
import { ApiError, describeError, networkError } from "@/lib/api/errors";
import type { Prediction } from "@/lib/api/types";
import { formatRelativeTime, formatStat } from "@/lib/format";
import { targetLabel } from "@/lib/models";
import { cn } from "@/lib/utils";

const ERROR_TITLES: Record<string, string> = {
  insufficient_data: "Not enough recent games for a forecast",
  game_already_started: "This game has started",
  invalid_matchup: "This player isn't in this game",
  model_unavailable: "Forecasts are unavailable right now",
};

/** Axis ceilings per statistic so every range reads on a sensible, fixed scale. */
const AXIS_MAX: Record<string, number> = { pts: 50, reb: 20, ast: 15, fg3m: 8, stl: 5, blk: 5, min: 48 };

function Inputs({ prediction, stat }: { prediction: Prediction; stat: string }) {
  const inputs = (
    prediction.explanation?.inputs as Record<string, Record<string, number | null>> | undefined
  )?.[stat];
  if (!inputs) return null;
  const parts = [
    ["last 5", inputs[`${stat}_avg_5`]],
    ["last 10", inputs[`${stat}_avg_10`]],
    ["season", inputs[`${stat}_season_avg`]],
    ["vs opponent", inputs[`${stat}_vs_opponent`]],
  ] as const;
  return (
    <p className="mt-1 text-footnote text-muted-foreground">
      Inputs: {parts.map(([label, value]) => `${label} ${formatStat(value ?? null)}`).join(" · ")}
    </p>
  );
}

const FRESHNESS: Record<Prediction["freshness"], string> = {
  current: "Up to date",
  stale: "Newer data available",
  invalid: "Matchup changed",
  superseded: "Newer forecast available",
  final_pregame: "Made before tip-off",
};

function ForecastView({
  prediction,
  onRefresh,
  pending,
}: {
  prediction: Prediction;
  onRefresh: () => void;
  pending: boolean;
}) {
  const stale = prediction.freshness === "stale" && !prediction.freshness_reason?.includes("release");
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-subhead">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5 font-medium">
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              prediction.freshness === "current" || prediction.freshness === "final_pregame"
                ? "bg-positive"
                : "bg-muted-foreground",
            )}
          />
          {FRESHNESS[prediction.freshness]}
        </span>
        {prediction.freshness_reason && (
          <span className="text-footnote text-muted-foreground">{prediction.freshness_reason}</span>
        )}
        {stale && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={pending}
            className="min-h-9 rounded-full border border-border px-4 text-subhead font-medium transition-colors hover:border-foreground/25 disabled:opacity-60"
          >
            {pending ? "Updating…" : "Update forecast"}
          </button>
        )}
      </div>
      <ul className="grid gap-x-8 gap-y-5 md:grid-cols-2">
        {prediction.values.map((v) => (
          <li key={v.stat}>
            <IntervalBar
              label={targetLabel(v.stat)}
              point={v.point}
              lower={v.lower}
              upper={v.upper}
              level={v.interval_level}
              max={Math.max(AXIS_MAX[v.stat] ?? 10, v.upper)}
            />
            <Inputs prediction={prediction} stat={v.stat} />
            {prediction.actuals?.[v.stat] != null && (
              <p className="mt-1 text-footnote">
                Actual{" "}
                <span className="font-semibold tabular-nums">{formatStat(prediction.actuals[v.stat])}</span>{" "}
                <span className="text-muted-foreground">
                  ·{" "}
                  {prediction.actuals[v.stat] >= v.lower && prediction.actuals[v.stat] <= v.upper
                    ? "inside"
                    : "outside"}{" "}
                  the range
                </span>
              </p>
            )}
          </li>
        ))}
      </ul>
      {prediction.double_double_probability != null && (
        <p className="text-subhead">
          Double-double chance:{" "}
          <span className="font-semibold tabular-nums">
            {Math.round(prediction.double_double_probability * 100)}%
          </span>
        </p>
      )}
      <p className="text-footnote text-muted-foreground">
        Release <span className="font-mono">{prediction.release_version}</span> · uses final games before{" "}
        {new Date(prediction.data_cutoff_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}{" "}
        · stored {formatRelativeTime(prediction.created_at)}. Each range is meant to contain the actual result
        4 times in 5. Inputs are the averages the model received, not a breakdown of its reasoning.
      </p>
    </div>
  );
}

/** Shows the stored forecast for this game, or makes one on request (stored before tip-off). */
export function Forecast({
  initial,
  playerId,
  gameId,
}: {
  initial: Prediction | null;
  playerId: number;
  gameId: string;
}) {
  const [prediction, setPrediction] = useState(initial);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, startTransition] = useTransition();

  function request() {
    setError(null);
    startTransition(async () => {
      try {
        setPrediction(await clientPost<Prediction>("/predictions", { player_id: playerId, game_id: gameId }));
      } catch (cause) {
        setError(cause instanceof ApiError ? cause : networkError(cause));
      }
    });
  }

  if (prediction) return <ForecastView prediction={prediction} onRefresh={request} pending={pending} />;
  if (error) {
    const known = ERROR_TITLES[error.code];
    const { title, message } = known ? { title: known, message: error.message } : describeError(error);
    return (
      <Unavailable kind={error.code === "insufficient_data" ? "no_games" : kindForError(error)} title={title}>
        {message}
      </Unavailable>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-dashed border-border p-5">
      <p className="min-w-0 flex-1 text-subhead text-muted-foreground">
        No forecast is stored for this game yet. One is made from final games so far and kept unchanged.
      </p>
      <button
        type="button"
        onClick={request}
        disabled={pending}
        className="min-h-10 rounded-full bg-primary px-5 text-subhead font-semibold text-primary-foreground transition-opacity disabled:opacity-60"
      >
        {pending ? "Forecasting…" : "Make forecast"}
      </button>
    </div>
  );
}
