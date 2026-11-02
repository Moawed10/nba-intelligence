"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { Unavailable, kindForError } from "@/components/data/unavailable";
import { clientPost } from "@/lib/api/client";
import { ApiError, describeError, networkError } from "@/lib/api/errors";
import type { PlayerGameLine, PredictedValue, Prediction } from "@/lib/api/types";
import { formatGameTime, formatRelativeTime, formatStat } from "@/lib/format";
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
const RECENT_GAMES = 5;

const round = (v: number) => Math.round(v);

/** Forecast range on the stat's own scale, with the player's real averages marked against it. */
function RangeScale({
  v,
  recent,
  season,
  label,
}: {
  v: PredictedValue;
  recent: number | null;
  season: number | null;
  label: string;
}) {
  const max = Math.max(v.upper, recent ?? 0, season ?? 0) * 1.1 || 1;
  const at = (x: number) => `${(x / max) * 100}%`;
  const range = `${Math.round(v.interval_level * 100)}% range`;
  const context = [
    recent != null ? `last 5 average ${formatStat(recent)}` : null,
    season != null ? `season average ${formatStat(season)}` : null,
  ].filter(Boolean);
  return (
    <div
      role="img"
      aria-label={`${label}: forecast ${formatStat(v.point)}, ${range} ${round(v.lower)} to ${round(v.upper)}${context.length ? `; ${context.join(", ")}` : ""}.`}
      className="relative mt-3 h-4"
    >
      <span className="absolute inset-x-0 top-1/2 h-px bg-border" />
      <span
        className="absolute inset-y-0.5 rounded-sm border border-dashed border-predicted bg-predicted/15"
        style={{ left: at(v.lower), width: `calc(${at(v.upper)} - ${at(v.lower)})` }}
      />
      {season != null && (
        <span
          className="absolute top-1/2 h-4 w-0.5 -translate-x-1/2 -translate-y-1/2 bg-actual"
          style={{ left: at(season) }}
        />
      )}
      {recent != null && (
        <span
          className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-actual"
          style={{ left: at(recent) }}
        />
      )}
      <span
        className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rotate-45 border-2 border-predicted bg-cell"
        style={{ left: at(v.point) }}
      />
    </div>
  );
}

function ScaleLegend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-footnote text-muted-foreground">
      <li className="flex items-center gap-2">
        <span aria-hidden className="size-2.5 rotate-45 border-2 border-predicted" />
        Forecast
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden className="h-2.5 w-5 rounded-sm border border-dashed border-predicted bg-predicted/15" />
        Likely range
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden className="size-2.5 rounded-full bg-actual" />
        Last 5 games, actual
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden className="h-3 w-0.5 bg-actual" />
        Season average, actual
      </li>
    </ul>
  );
}

function ForecastView({
  prediction,
  playerName,
  opponentName,
  onRefresh,
  pending,
  history,
  seasonAverages,
}: {
  prediction: Prediction;
  playerName: string;
  opponentName: string;
  onRefresh: () => void;
  pending: boolean;
  history: PlayerGameLine[];
  seasonAverages: Record<string, number | null> | null;
}) {
  const value = Object.fromEntries(prediction.values.map((v) => [v.stat, v]));
  const pts = value.pts;
  const stale = prediction.freshness === "stale" && !prediction.freshness_reason?.includes("release");
  const inputs = prediction.explanation?.inputs as Record<string, Record<string, number | null>> | undefined;
  const actual = prediction.actuals;
  const lastFive = history.slice(0, RECENT_GAMES);
  const recentAverage = (stat: (typeof HEADLINE)[number]) =>
    lastFive.length ? lastFive.reduce((sum, g) => sum + g.box[stat], 0) / lastFive.length : null;
  return (
    <div className="space-y-6">
      {pts && (
        <p className="max-w-3xl text-title3 leading-snug">
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
        <div className="flex flex-wrap items-center gap-3 rounded-lg bg-muted/60 px-4 py-3 text-subhead">
          <span>New games have been played since this forecast was made.</span>
          <button type="button" onClick={onRefresh} disabled={pending} className="btn btn-primary">
            {pending ? "Updating…" : "Update forecast"}
          </button>
        </div>
      )}
      <div className="space-y-3">
        <dl className="stat-grid sm:grid-cols-3">
          {HEADLINE.map((stat) => {
            const v = value[stat];
            if (!v) return null;
            const recent = recentAverage(stat);
            const season = seasonAverages?.[stat] ?? null;
            return (
              <div key={stat} className="p-4 sm:p-5">
                <dt className="kicker flex items-center justify-between gap-2">
                  {targetLabel(stat)}
                  <span className="rounded-sm border border-dashed border-predicted px-1 text-primary">Forecast</span>
                </dt>
                <dd>
                  <span className="numeral mt-2 block text-[clamp(3.5rem,8vw,5rem)] text-primary">
                    {formatStat(v.point)}
                  </span>
                  <span className="mt-1 block text-subhead font-medium tabular-nums">
                    Usually {round(v.lower)}–{round(v.upper)}
                  </span>
                  <RangeScale v={v} recent={recent} season={season} label={targetLabel(stat)} />
                  <span className="mt-3 grid grid-cols-2 gap-2 text-footnote text-muted-foreground tabular-nums">
                    <span>
                      Last {lastFive.length || RECENT_GAMES}
                      <span className="block font-semibold text-foreground">{formatStat(recent)}</span>
                    </span>
                    <span>
                      Season
                      <span className="block font-semibold text-foreground">{formatStat(season)}</span>
                    </span>
                  </span>
                  {actual?.[stat] != null && (
                    <span className="mt-2 block border-t border-border pt-2 text-footnote">
                      Actual: <strong>{actual[stat]}</strong>
                    </span>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
        <ScaleLegend />
      </div>
      <RecentRange games={history} values={value} firstName={playerName.split(" ")[0]} />
      <dl className="stat-grid grid-cols-2 sm:grid-cols-4">
        {SECONDARY.map((stat) => {
          const v = value[stat];
          if (!v) return null;
          return (
            <div key={stat} className="px-3 py-2.5">
              <dt className="text-footnote text-muted-foreground">{targetLabel(stat)}</dt>
              <dd className="numeral mt-1 text-title1">{formatStat(v.point)}</dd>
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
      <section aria-labelledby="forecast-factors" className="space-y-3 border-t border-border pt-4 text-subhead">
        <h3 id="forecast-factors" className="kicker">
          What is this based on?
        </h3>
        <p className="max-w-3xl text-muted-foreground">
          How {playerName} has played lately, this season, and in past games against the {opponentName}, plus
          rest and whether the game is at home. About 4 games out of 5, the real number lands inside the
          &quot;usually&quot; range.
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
          Model <span className="font-mono">{prediction.release_version}</span> · Data through{" "}
          {formatGameTime(prediction.data_cutoff_at)} · Updated {formatRelativeTime(prediction.created_at)} ·{" "}
          <Link href="/models" className="text-primary underline underline-offset-2">
            How accurate are these forecasts?
          </Link>
        </p>
      </section>
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
  seasonAverages,
}: {
  initial: Prediction | null;
  unavailable?: { code: string; message: string } | null;
  playerId: number;
  gameId: string;
  playerName: string;
  opponentName: string;
  /** The player's most recent regular-season games, newest first. */
  history: PlayerGameLine[];
  /** Current-season per-game values for context; null when the player has none. */
  seasonAverages: Record<string, number | null> | null;
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
        history={history}
        seasonAverages={seasonAverages}
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
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-muted/40 p-5">
      <p className="min-w-0 flex-1 text-subhead text-muted-foreground">No forecast for this game yet.</p>
      <button
        type="button"
        onClick={request}
        disabled={pending}
        className="btn btn-primary"
      >
        {pending ? "Forecasting…" : "Make forecast"}
      </button>
    </div>
  );
}
