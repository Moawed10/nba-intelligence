import Link from "next/link";

import { ApiErrorView } from "@/components/data/api-error";
import { InfoHint } from "@/components/data/info-hint";
import { Panel } from "@/components/data/panel";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type {
  LiveAccuracy,
  ModelAnalytics,
  ModelReleaseDetail,
  ModelReleaseSummary,
  TargetMetrics,
} from "@/lib/api/types";
import { formatGameDate, formatPercent } from "@/lib/format";
import { algorithmLabel, TARGET_ORDER, targetLabel } from "@/lib/models";
import { param, type SearchParams } from "@/lib/url";
import { cn } from "@/lib/utils";

import { AlgorithmComparison } from "./algorithms";
import { PredictionCheck, PredictionHistoryExplorer } from "./analytics";
import { ModelsNav } from "./models-nav";

const VERSION = /^\d{4}\.\d{2}\.\d{2}-\d{1,3}$/;

interface Calibration {
  alpha: number;
  edges: number[];
  quantiles: number[];
  counts: number[];
}

const FEATURE_GROUPS: { label: string; test: (name: string) => boolean }[] = [
  {
    label: "Recent form (last 3, 5 and 10 games)",
    test: (n) => /_avg_\d+$/.test(n) && !n.startsWith("usage"),
  },
  { label: "Season to date", test: (n) => n.endsWith("_season_avg") || n === "season_games" },
  { label: "Trend, volatility and usage", test: (n) => /_trend$|_std_\d+$|^usage/.test(n) },
  {
    label: "Schedule and rest",
    test: (n) => ["is_home", "rest_days", "is_back_to_back", "team_rest_days"].includes(n),
  },
  { label: "Opponent and pace", test: (n) => n.startsWith("opp_") || n.startsWith("team_pace") },
  { label: "History against this opponent", test: (n) => n.endsWith("_vs_opponent") },
];

function StatusBadge({ status }: { status: string }) {
  const active = status === "active";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-footnote font-medium",
        active ? "bg-muted text-foreground" : "bg-muted text-muted-foreground",
      )}
    >
      {active && <span aria-hidden className="size-1.5 rounded-full bg-positive" />}
      {active
        ? "Serving predictions"
        : status === "candidate"
          ? "Candidate · not serving predictions yet"
          : status}
    </span>
  );
}

function Timeline({ release, testSeason }: { release: ModelReleaseDetail; testSeason: string }) {
  const segments = [
    { label: "Learning", start: release.train_start, end: release.train_end, tone: "bg-chart-3" },
    { label: "Tryout", start: release.val_start, end: release.val_end, tone: "bg-chart-2" },
    { label: `Test · ${testSeason}`, start: release.test_start, end: release.test_end, tone: "bg-primary" },
  ];
  const t = (d: string) => new Date(`${d}T00:00:00Z`).getTime();
  const span = t(release.test_end) - t(release.train_start);
  return (
    <div>
      <div aria-hidden className="flex h-2.5 gap-1 overflow-hidden rounded-full">
        {segments.map((s) => (
          <span
            key={s.label}
            className={cn("rounded-full", s.tone)}
            style={{ flexGrow: (t(s.end) - t(s.start)) / span }}
          />
        ))}
      </div>
      <ol className="mt-3 grid gap-3 sm:grid-cols-3">
        {segments.map((s) => (
          <li key={s.label} className="flex gap-2">
            <span aria-hidden className={cn("mt-1.5 size-2 shrink-0 rounded-full", s.tone)} />
            <span>
              <span className="block text-subhead font-medium">{s.label}</span>
              <span className="text-footnote text-muted-foreground">
                {formatGameDate(s.start, true)} – {formatGameDate(s.end, true)}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function AccuracyTable({ metrics, testSeason }: { metrics: TargetMetrics[]; testSeason: string }) {
  const rows = TARGET_ORDER.flatMap((t) => metrics.filter((m) => m.target === t));
  const gain = (m: TargetMetrics) =>
    m.mae != null && m.baseline_mae ? (m.baseline_mae - m.mae) / m.baseline_mae : null;
  const maxGain = Math.max(0.0001, ...rows.map((m) => gain(m) ?? 0));
  return (
    <div role="region" aria-label="Accuracy by statistic" tabIndex={0} className="overflow-x-auto">
      <table className="w-full min-w-[44rem] text-subhead tabular-nums">
        <caption className="sr-only">
          Accuracy of each selected model on {testSeason}, a season none of the models saw while training
        </caption>
        <thead className="text-footnote text-muted-foreground">
          <tr className="border-b border-border">
            <th scope="col" className="py-2 text-left font-medium">
              Statistic
            </th>
            <th scope="col" className="py-2 text-left font-medium">
              Model
            </th>
            <th scope="col" className="py-2 pl-4 text-right font-medium">
              Avg miss
            </th>
            <th scope="col" className="py-2 pl-4 text-right font-medium">
              Simple average miss
            </th>
            <th scope="col" className="w-36 py-2 pl-4 text-left font-medium">
              Improvement
            </th>
            <th scope="col" className="py-2 pl-4 text-right font-medium">
              Typical big miss
            </th>
            <th scope="col" className="py-2 pl-4 text-right font-medium">
              In 80% range
            </th>
            <th scope="col" className="py-2 pl-4 text-right font-medium">
              Stat lines checked
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => {
            const g = gain(m);
            const baselineKept = m.algorithm === "rolling_baseline";
            return (
              <tr key={m.target} className="border-b border-border/50 last:border-0">
                <th scope="row" className="py-2 text-left font-medium">
                  {targetLabel(m.target)}
                </th>
                <td className="py-2 text-left text-muted-foreground">{algorithmLabel(m.algorithm)}</td>
                <td className="py-2 text-right font-semibold">{m.mae?.toFixed(2) ?? "—"}</td>
                <td className="py-2 text-right text-muted-foreground">{m.baseline_mae?.toFixed(2) ?? "—"}</td>
                <td className="py-2 pl-4">
                  {baselineKept ? (
                    <span className="text-footnote text-muted-foreground">Simple average kept</span>
                  ) : g == null ? (
                    "—"
                  ) : (
                    <span className="flex items-center gap-2">
                      <span
                        aria-hidden
                        className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
                      >
                        <span
                          className={cn(
                            "absolute inset-y-0 left-0 rounded-full",
                            g > 0 ? "bg-positive" : "bg-negative",
                          )}
                          style={{ width: `${(Math.max(0, g) / maxGain) * 100}%` }}
                        />
                      </span>
                      <span
                        className={cn(
                          "w-12 text-right text-footnote",
                          g > 0 ? "text-positive" : "text-negative",
                        )}
                      >
                        {(g * 100).toFixed(1)}%
                      </span>
                    </span>
                  )}
                </td>
                <td className="py-2 text-right text-muted-foreground">{m.rmse?.toFixed(2) ?? "—"}</td>
                <td className="py-2 text-right">{formatPercent(m.interval_coverage)}</td>
                <td className="py-2 text-right text-muted-foreground">{m.n.toLocaleString("en-US")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RangesTable({ calibration }: { calibration: Record<string, Calibration> }) {
  const targets = TARGET_ORDER.filter((t) => calibration[t]);
  const first = calibration[targets[0]];
  const edges = first.edges.map((e) => e.toFixed(1));
  const bins = [`< ${edges[0]}`, `${edges[0]}–${edges[1]}`, `> ${edges[1]}`];
  return (
    <div role="region" aria-label="Prediction range widths" tabIndex={0} className="overflow-x-auto">
      <table className="w-full text-subhead tabular-nums">
        <caption className="sr-only">
          Half-width of the {Math.round((1 - first.alpha) * 100)}% prediction range by predicted minutes
        </caption>
        <thead className="text-footnote text-muted-foreground">
          <tr>
            <td />
            <th scope="colgroup" colSpan={3} className="pt-1 text-right font-medium">
              Predicted minutes
            </th>
          </tr>
          <tr className="border-b border-border">
            <th scope="col" className="py-2 text-left font-medium">
              Statistic
            </th>
            {bins.map((b) => (
              <th key={b} scope="col" className="py-2 pl-4 text-right font-medium">
                {b}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {targets.map((t) => (
            <tr key={t} className="border-b border-border/50 last:border-0">
              <th scope="row" className="py-2 text-left font-normal">
                {targetLabel(t)}
              </th>
              {calibration[t].quantiles.map((q, i) => (
                <td key={i} className="py-2 text-right">
                  ±{q.toFixed(1)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FeatureList({ features }: { features: string[] }) {
  const grouped = FEATURE_GROUPS.map((g) => ({ ...g, names: features.filter(g.test) }));
  const other = features.filter((f) => !FEATURE_GROUPS.some((g) => g.test(f)));
  if (other.length) grouped.push({ label: "Other", test: () => false, names: other });
  return (
    <details className="group">
      <summary className="cursor-pointer py-3 text-subhead font-medium text-primary hover:underline">
        Show all {features.length} inputs
      </summary>
      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        {grouped
          .filter((g) => g.names.length)
          .map((g) => (
            <div key={g.label}>
              <h3 className="kicker mb-2">
                {g.label} · {g.names.length}
              </h3>
              <ul className="flex flex-wrap gap-1.5">
                {g.names.map((n) => (
                  <li key={n} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-footnote">
                    {n}
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </div>
    </details>
  );
}

function LiveGameScores({ scores }: { scores: NonNullable<LiveAccuracy["game_scores"]> }) {
  const facts = [
    ["Average score miss", `${scores.points_mae.toFixed(2)} pts`],
    ["Scores inside the range", formatPercent(scores.interval_coverage)],
    ["Picked the winner", formatPercent(scores.winner_accuracy)],
    ["Win chance Brier score", scores.brier.toFixed(3)],
  ];
  return (
    <section aria-labelledby="live-game-scores" className="space-y-3">
      <h3 id="live-game-scores" className="kicker">
        Final-score forecasts, {scores.games} {scores.games === 1 ? "game" : "games"}
      </h3>
      <dl className="grid grid-cols-2 gap-3">
        {facts.map(([term, value]) => (
          <div key={term} className="rounded-xl bg-muted/40 px-4 py-3">
            <dt className="text-footnote text-muted-foreground">{term}</dt>
            <dd className="numeral text-title3">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-footnote text-muted-foreground">
        Each game counts once, using the last forecast made before tip-off. These are real games, kept
        separate from the held-out season.
      </p>
    </section>
  );
}

function LiveTable({ live, heldOut }: { live: LiveAccuracy; heldOut: TargetMetrics[] }) {
  const reference = new Map(heldOut.map((m) => [m.target, m.mae]));
  return (
    <div className="space-y-3">
      <div role="region" aria-label="Live accuracy by statistic" tabIndex={0} className="overflow-x-auto">
        <table className="w-full text-subhead tabular-nums">
          <caption className="sr-only">
            Average miss of final pregame forecasts after {live.games} games, next to the test season
          </caption>
          <thead className="text-footnote text-muted-foreground">
            <tr className="border-b border-border">
              <th scope="col" className="py-2 text-left font-medium">
                Statistic
              </th>
              <th scope="col" className="py-2 pl-4 text-right font-medium">
                Live miss
              </th>
              <th scope="col" className="py-2 pl-4 text-right font-medium">
                Held-out miss
              </th>
              <th scope="col" className="py-2 pl-4 text-right font-medium">
                In range
              </th>
              <th scope="col" className="py-2 pl-4 text-right font-medium">
                Forecasts
              </th>
            </tr>
          </thead>
          <tbody>
            {live.stats.map((s) => (
              <tr key={s.stat} className="border-b border-border/50 last:border-0">
                <th scope="row" className="py-2 text-left font-normal">
                  {targetLabel(s.stat)}
                </th>
                <td className="py-2 text-right font-semibold">{s.mae?.toFixed(2) ?? "—"}</td>
                <td className="py-2 text-right text-muted-foreground">
                  {reference.get(s.stat)?.toFixed(2) ?? "—"}
                </td>
                <td className="py-2 text-right">{formatPercent(s.interval_coverage)}</td>
                <td className="py-2 text-right text-muted-foreground">{s.n.toLocaleString("en-US")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-footnote text-muted-foreground">
        Each player-game counts once, using the last forecast made before tip-off, across {live.games}{" "}
        {live.games === 1 ? "game" : "games"}.
        {live.double_double?.brier != null &&
          ` Double-double chances: error score ${live.double_double.brier.toFixed(3)} over ${live.double_double.n} forecasts, where 0 is perfect.`}{" "}
        Small samples swing widely; compare with the test season only after many games.
      </p>
    </div>
  );
}

export async function ModelsView({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const query = await searchParams;
  const list = await serverTry<ModelReleaseSummary[]>("/models");
  if (list.error) return <ApiErrorView error={list.error} />;
  const releases = list.data;
  if (releases.length === 0) {
    return (
      <Unavailable kind="no_model" title="No model has been trained yet">
        Accuracy appears here after the first training run is evaluated on a season the models never saw.
      </Unavailable>
    );
  }
  const requested = param(query, "version");
  const known = requested && VERSION.test(requested) && releases.some((r) => r.version === requested);
  const version = known ? requested : (releases.find((r) => r.status === "active") ?? releases[0]).version;
  const [result, liveResult, analytics] = await Promise.all([
    serverTry<ModelReleaseDetail>(`/models/${version}`),
    serverTry<LiveAccuracy>(`/models/${version}/live`),
    serverTry<ModelAnalytics>(`/models/${version}/analytics`, { stat: "pts", kind: "backtest" }),
  ]);
  const live = liveResult.data;
  if (result.error) return <ApiErrorView error={result.error} />;
  const release = result.data;
  const testSeason = release.test_season ?? "the test season";
  const regression = release.selected_metrics.filter((m) => m.target !== "double_double");
  const doubleDouble = release.selected_metrics.find((m) => m.target === "double_double");
  const calibration = release.interval_calibration as unknown as Record<string, Calibration>;
  const active = release.status === "active";

  return (
    <div className="xl:grid xl:grid-cols-[13rem_minmax(0,1fr)] xl:gap-8">
      <aside aria-label="Model sections" className="hidden xl:block">
        <ModelsNav />
      </aside>
      <div className="grid gap-5 lg:grid-cols-12">
        {requested && !known && (
          <Unavailable kind="empty" title={`No release named ${requested}`} className="lg:col-span-12">
            Showing the latest release instead.
          </Unavailable>
        )}
        <Panel
          id="release"
          kicker="Release"
          title={<span className="font-mono">{release.version}</span>}
          actions={<StatusBadge status={release.status} />}
          className="lg:col-span-12"
        >
          <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
            <Timeline release={release} testSeason={testSeason} />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-subhead sm:grid-cols-4 lg:grid-cols-2">
              {[
                ["Trained", formatGameDate(release.created_at.slice(0, 10), true)],
                ["Inputs", String(release.features.length)],
              ].map(([term, value]) => (
                <div key={term}>
                  <dt className="text-footnote text-muted-foreground">{term}</dt>
                  <dd className="font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
          <p className="mt-5 text-footnote text-muted-foreground">
            Seasons stay in date order. Models learn from the earlier seasons, the best one is chosen on the
            tryout season, and it is scored once on {testSeason}. Every input uses only games played before
            the one being predicted.
          </p>
          <details className="mt-1 text-footnote text-muted-foreground">
            <summary className="cursor-pointer py-3.5 font-medium">Technical details</summary>
            <p className="mt-2">
              Data version {release.data_version}
              {release.git_sha && (
                <>
                  {" · Code "}
                  <span className="font-mono">{release.git_sha.slice(0, 7)}</span>
                </>
              )}
            </p>
          </details>
        </Panel>

        <Panel
          id="accuracy"
          kicker={`Tested on ${testSeason}`}
          title="Accuracy against a simple average"
          actions={
            <InfoHint term="Average miss">
              How far the prediction lands from the actual box score, on average. The
              simple average predicts each player&apos;s average over the previous 10 games.
            </InfoHint>
          }
          className="lg:col-span-12"
        >
          {regression.length ? (
            <AccuracyTable metrics={regression} testSeason={testSeason} />
          ) : (
            <Unavailable kind="not_built" title="No test-season results recorded for this release" />
          )}
        </Panel>

        <Panel
          id="algorithms"
          kicker="Picking a model"
          title="Models compared"
          className="lg:col-span-7"
        >
          {release.algorithms.length ? (
            <AlgorithmComparison algorithms={release.algorithms} testSeason={testSeason} />
          ) : (
            <Unavailable kind="not_built" title="No candidate algorithms recorded" />
          )}
        </Panel>

        <Panel id="ranges" kicker="Uncertainty" title="Prediction ranges" className="lg:col-span-5">
          {Object.keys(calibration).length ? (
            <div className="space-y-4">
              <p className="text-subhead">
                Each prediction comes with a range meant to contain the actual result 4 times in 5. Ranges
                widen for players expected to play more minutes.
              </p>
              <RangesTable calibration={calibration} />
              <p className="text-footnote text-muted-foreground">
                Ranges are sized by how many minutes a player is expected to play, using {testSeason} for the
                models now serving. Ranges set on the tryout season and checked on {testSeason} held{" "}
                {formatPercent(Math.min(...regression.map((m) => m.interval_coverage ?? 1)))}–
                {formatPercent(Math.max(...regression.map((m) => m.interval_coverage ?? 0)))} of results.
              </p>
            </div>
          ) : (
            <Unavailable kind="not_built" title="No prediction ranges stored for this release" />
          )}
        </Panel>

        <Panel
          id="check"
          kicker="Every prediction, scored"
          title="Check the predictions"
          className="lg:col-span-12"
        >
          <PredictionCheck version={release.version} testSeason={testSeason} initial={analytics.data} />
        </Panel>

        <Panel id="explorer" kicker="Game by game" title="Prediction history" className="lg:col-span-12">
          <PredictionHistoryExplorer testSeason={testSeason} />
        </Panel>

        <Panel id="live" kicker="After release" title="Live accuracy" className="lg:col-span-7">
          {live && (live.games > 0 || live.game_scores) ? (
            <div className="space-y-6">
              {live.games > 0 && <LiveTable live={live} heldOut={regression} />}
              {live.game_scores && <LiveGameScores scores={live.game_scores} />}
            </div>
          ) : (
            <Unavailable
              kind={active ? "empty" : "not_built"}
              title={active ? "No scored predictions yet" : "Starts when a release is activated"}
            >
              Predictions are stored before tip-off and scored against the final box score.{" "}
              {active
                ? "Scored results appear here once games with stored predictions are final."
                : "This release has not served predictions, so there is no live record to show."}
            </Unavailable>
          )}
        </Panel>
        <Panel id="double-double" kicker="Probability" title="Double-double" className="lg:col-span-5">
          {doubleDouble?.brier != null ? (
            <div className="space-y-3">
              <dl className="grid grid-cols-3 gap-3 text-center">
                {[
                  ["Error score", doubleDouble.brier.toFixed(3)],
                  ["Overconfidence score", doubleDouble.log_loss?.toFixed(3) ?? "—"],
                  ["Stat lines checked", doubleDouble.n.toLocaleString("en-US")],
                ].map(([term, value]) => (
                  <div key={term} className="rounded-lg bg-muted/60 p-3">
                    <dt className="text-footnote text-muted-foreground">{term}</dt>
                    <dd className="text-title3 font-semibold tabular-nums">{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="text-footnote text-muted-foreground">
                {algorithmLabel(doubleDouble.algorithm)} with its chances adjusted to match how often double-doubles
                really happened, scored on {testSeason}. Lower is better on both scores, and the overconfidence
                score punishes being sure and wrong the most. Technical names: Brier score and log loss.
              </p>
            </div>
          ) : (
            <Unavailable kind="not_built" title="No double-double evaluation recorded" />
          )}
        </Panel>

        <Panel id="inputs" kicker="Features" title="What the models see" className="lg:col-span-12">
          <FeatureList features={release.features} />
        </Panel>

        <Panel id="history" kicker="Registry" title="Releases" className="lg:col-span-12">
          <ul className="divide-y divide-border">
            {releases.map((r) => (
              <li key={r.version} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <span className="flex items-center gap-3">
                  {r.version === version ? (
                    <span className="font-mono font-semibold" aria-current="true">
                      {r.version}
                    </span>
                  ) : (
                    <Link
                      href={`/models?version=${r.version}`}
                      className="font-mono text-primary hover:underline"
                    >
                      {r.version}
                    </Link>
                  )}
                  <StatusBadge status={r.status} />
                </span>
                <span className="text-footnote text-muted-foreground">
                  Trained {formatGameDate(r.created_at.slice(0, 10), true)} · test {r.test_start.slice(0, 4)}–
                  {r.test_end.slice(0, 4)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
