"use client";

import { useState, useTransition } from "react";

import { Unavailable, kindForError } from "@/components/data/unavailable";
import { clientPost } from "@/lib/api/client";
import { ApiError, describeError, networkError } from "@/lib/api/errors";
import type { PlayerGameLine, Prediction } from "@/lib/api/types";
import { formatRelativeTime, formatStat } from "@/lib/format";
import { targetLabel } from "@/lib/models";

import { RecentRange } from "./recent-range";

const ERROR_TITLES: Record<string, string> = {
  insufficient_data: "Not enough recent games for a forecast",
  game_already_started: "This game has started",
  invalid_matchup: "This player isn't in this game",
  model_unavailable: "Forecasts are unavailable right now",
};

const HEADLINE = ["pts", "reb", "ast"] as const;
const SECONDARY = ["fg3m", "stl", "blk", "min"] as const;

const round = (v: number) => Math.round(v);

function ForecastView({
  prediction,
  playerName,
  opponentName,
  onRefresh,
  pending,
  error,
  history,
}: {
  prediction: Prediction;
  playerName: string;
  opponentName: string;
  onRefresh: () => void;
  pending: boolean;
  error: ApiError | null;
  history: PlayerGameLine[];
}) {
  const value = Object.fromEntries(prediction.values.map((v) => [v.stat, v]));
  const pts = value.pts;
  const stale = prediction.freshness === "stale" && !prediction.freshness_reason?.includes("release");
  const inputs = prediction.explanation?.inputs as Record<string, Record<string, number | null>> | undefined;
  const actual = prediction.actuals;
  return (
    <div className="space-y-5">
      {pts && (
        <p className="text-title3 leading-snug">
          Against the {opponentName}, {playerName} is expected to score about{" "}
          <strong className="text-primary">{round(pts.point)} points</strong>
          {value.reb && value.ast && (
            <>
              {" "}
              with about {round(value.reb.point)} rebounds and {round(value.ast.point)} assists
            </>
          )}
          .
        </p>
      )}
      {stale && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl bg-muted/60 px-4 py-3 text-subhead">
          <span>New games have been played since this forecast was made.</span>
          <button
            type="button"
            onClick={onRefresh}
            disabled={pending}
            className="min-h-9 rounded-full bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-60"
          >
            {pending ? "Updating…" : "Update forecast"}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="rounded-xl bg-muted/60 px-4 py-3 text-subhead">
          <strong>{ERROR_TITLES[error.code] ?? "This forecast couldn't be updated"}.</strong>{" "}
          {ERROR_TITLES[error.code] ? error.message : describeError(error).message}
        </p>
      )}
      <dl className="grid gap-3 sm:grid-cols-3">
        {HEADLINE.map((stat) => {
          const v = value[stat];
          if (!v) return null;
          return (
            <div key={stat} className="rounded-2xl border border-border bg-muted/40 p-4">
              <dt className="kicker">{targetLabel(stat)}</dt>
              <dd>
                <span className="numeral block text-[3.25rem]">{formatStat(v.point)}</span>
                <span className="text-footnote text-muted-foreground">
                  Usually {round(v.lower)}–{round(v.upper)}
                </span>
                {actual?.[stat] != null && (
                  <span className="mt-1 block text-footnote">
                    Actual: <strong>{actual[stat]}</strong>
                  </span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
      <RecentRange games={history} values={value} firstName={playerName.split(" ")[0]} />
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {SECONDARY.map((stat) => {
          const v = value[stat];
          if (!v) return null;
          return (
            <div key={stat} className="rounded-xl bg-muted/40 px-3 py-2.5">
              <dt className="text-footnote text-muted-foreground">{targetLabel(stat)}</dt>
              <dd className="numeral text-title2">{formatStat(v.point)}</dd>
            </div>
          );
        })}
      </dl>
      {prediction.double_double_probability != null && (
        <p className="text-subhead">
          Chance of a double-double (10+ in two categories):{" "}
          <strong>{Math.round(prediction.double_double_probability * 100)}%</strong>
        </p>
      )}
      <details className="group rounded-xl border border-border px-4 py-3 text-subhead">
        <summary className="cursor-pointer font-medium text-primary">What is this based on?</summary>
        <div className="mt-3 space-y-4">
          <p className="text-muted-foreground">
            We look at how {playerName} has played lately, this season, and in past games against the{" "}
            {opponentName}, plus rest and whether the game is at home. Most of the time, about 4 games out of
            5, the real number lands inside the &quot;usually&quot; range.
          </p>
          {inputs && (
            <div className="space-y-2">
              {HEADLINE.map((stat) => {
                const row = inputs[stat];
                if (!row) return null;
                const facts = [
                  ["Recent games", row[`${stat}_avg_5`]],
                  ["This season", row[`${stat}_season_avg`]],
                  [`Vs ${opponentName}`, row[`${stat}_vs_opponent`]],
                ] as const;
                return (
                  <div key={stat} className="flex flex-wrap items-center gap-2">
                    <span className="w-20 font-medium">{targetLabel(stat)}</span>
                    {facts.map(([label, v]) => (
                      <span key={label} className="rounded-full bg-muted px-3 py-1 text-footnote">
                        {label} <strong className="text-foreground">{v == null ? "—" : Math.round(v)}</strong>
                      </span>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-footnote text-muted-foreground">
            Updated {formatRelativeTime(prediction.created_at)}.{" "}
            <a href="/models" className="text-primary hover:underline">
              How accurate are these forecasts?
            </a>
          </p>
        </div>
      </details>
    </div>
  );
}

/** The forecast for one game in plain language; technical detail sits behind a disclosure. */
export function Forecast({
  initial,
  unavailable,
  playerId,
  gameId,
  playerName,
  opponentName,
  history,
}: {
  initial: Prediction | null;
  unavailable?: { code: string; message: string } | null;
  playerId: number;
  gameId: string;
  playerName: string;
  opponentName: string;
  /** The player's most recent regular-season games, newest first. */
  history: PlayerGameLine[];
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

  if (prediction) {
    return (
      <ForecastView
        prediction={prediction}
        playerName={playerName}
        opponentName={opponentName}
        onRefresh={request}
        pending={pending}
        error={error}
        history={history}
      />
    );
  }
  const reason = error ?? (unavailable ? new ApiError(422, unavailable.code, unavailable.message) : null);
  if (reason) {
    const known = ERROR_TITLES[reason.code];
    const { title, message } = known ? { title: known, message: reason.message } : describeError(reason);
    return (
      <Unavailable
        kind={reason.code === "insufficient_data" ? "no_games" : kindForError(reason)}
        title={title}
      >
        {message}
      </Unavailable>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-dashed border-border p-5">
      <p className="min-w-0 flex-1 text-subhead text-muted-foreground">No forecast for this game yet.</p>
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
