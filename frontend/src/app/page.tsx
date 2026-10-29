import Link from "next/link";
import { Suspense } from "react";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { ApiErrorView } from "@/components/data/api-error";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { InfoHint } from "@/components/data/info-hint";
import { PageHeader } from "@/components/data/page-header";
import { Panel } from "@/components/data/panel";
import { LoadingBlock } from "@/components/data/state-view";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { DatasetStatus, ModelSnapshot, Overview, Standouts } from "@/lib/api/types";
import { formatGameDate, formatPercent, formatStat } from "@/lib/format";
import { TARGET_ORDER, targetLabel } from "@/lib/models";
import { cn } from "@/lib/utils";

import { LeadersBoard, ScheduleBoard } from "./_overview/interactive";

const DATASET_LABELS: Record<string, string> = {
  schedule: "Schedule",
  final_box_scores: "Box scores",
  player_game_logs: "Game logs",
  season_stats: "Season stats",
  team_stats: "Team stats",
  player_metadata: "Rosters",
};

function StandoutGrid({ standouts }: { standouts: Standouts }) {
  if (standouts.performances.length === 0) {
    return (
      <Unavailable kind="empty" title="No completed games yet">
        Standout lines appear after the first final box scores.
      </Unavailable>
    );
  }
  return (
    <ol className="stagger grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {standouts.performances.map((p, index) => {
        const line = [
          ["PTS", p.box.pts],
          ["REB", p.box.reb],
          ["AST", p.box.ast],
          ["FG", `${p.box.fgm}–${p.box.fga}`],
        ] as const;
        return (
          <li key={`${p.game_id}-${p.player_id}`}>
            <Link
              href={`/players/${p.player_id}`}
              className="group relative flex h-full flex-col gap-3 overflow-hidden rounded-xl border border-border bg-card p-4 transition-colors hover:border-foreground/25"
            >
              <span
                aria-hidden
                className="absolute inset-x-0 top-0 h-0.5"
                style={{ background: p.team.primary_color ?? "var(--border)" }}
              />
              <span className="flex items-center gap-3">
                <PlayerAvatar id={p.player_id} name={p.full_name} team={p.team} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold group-hover:text-primary">{p.full_name}</span>
                  <span className="block truncate text-footnote text-muted-foreground">
                    {p.team.abbreviation} {p.is_home ? "vs" : "@"} {p.opponent.abbreviation} ·{" "}
                    {formatGameDate(p.game_date)}
                    {p.result && ` · ${p.result}`}
                  </span>
                </span>
                <span className="kicker text-primary">#{index + 1}</span>
              </span>
              <span className="grid grid-cols-4 gap-2 text-center">
                {line.map(([label, value]) => (
                  <span key={label}>
                    <span className="kicker block">{label}</span>
                    <span
                      className={cn(
                        "block font-semibold tabular-nums",
                        label === "FG" ? "text-headline leading-7" : "text-title2",
                      )}
                    >
                      {value}
                    </span>
                  </span>
                ))}
              </span>
              <span className="mt-auto flex items-center justify-between text-footnote text-muted-foreground">
                <span>Game Score {formatStat(p.game_score)}</span>
                {p.double_double && (
                  <span className="rounded-full bg-primary/15 px-2 py-0.5 font-medium text-primary">
                    Double-double
                  </span>
                )}
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

function ModelPanel({ model }: { model: ModelSnapshot | null }) {
  if (!model) {
    return (
      <Unavailable kind="no_model" title="No model has been trained yet">
        Accuracy appears here after the first training run is evaluated on a held-out season.
      </Unavailable>
    );
  }
  const regression = TARGET_ORDER.flatMap((t) => model.metrics.filter((m) => m.target === t));
  const doubleDouble = model.metrics.find((m) => m.target === "double_double");
  const serving = model.release.status === "active";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-footnote">
        <span className="font-mono text-subhead">{model.release.version}</span>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-medium",
            serving ? "bg-muted text-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          {serving && <span aria-hidden className="size-1.5 rounded-full bg-positive" />}
          {serving ? "Serving predictions" : "Candidate · not serving predictions yet"}
        </span>
        <span className="text-muted-foreground">Scored on {model.test_season} games it never saw</span>
      </div>
      <table className="w-full text-subhead">
        <caption className="sr-only">
          Mean absolute error per statistic for the model and the baseline, {model.test_season}
        </caption>
        <thead className="text-footnote text-muted-foreground">
          <tr className="border-b border-border">
            <th scope="col" className="py-1.5 text-left font-medium">
              Statistic
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              Model error
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              Baseline error
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              In 80% range
            </th>
          </tr>
        </thead>
        <tbody>
          {regression.map((m) => {
            const better = m.mae != null && m.baseline_mae != null && m.mae < m.baseline_mae;
            return (
              <tr key={m.target} className="border-b border-border/50 last:border-0">
                <th scope="row" className="py-1.5 text-left font-normal">
                  {targetLabel(m.target)}
                </th>
                <td className={cn("py-1.5 text-right tabular-nums", better && "font-semibold")}>
                  {m.mae?.toFixed(2) ?? "—"}
                </td>
                <td className="py-1.5 text-right text-muted-foreground tabular-nums">
                  {m.baseline_mae?.toFixed(2) ?? "—"}
                </td>
                <td className="py-1.5 text-right tabular-nums">{formatPercent(m.interval_coverage)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-footnote text-muted-foreground">
        Error is the average miss per game (mean absolute error). The baseline predicts each player&apos;s
        average over their previous 10 games.
        {doubleDouble?.brier != null &&
          ` Double-double probability: Brier score ${doubleDouble.brier.toFixed(3)} over ${doubleDouble.n.toLocaleString("en-US")} player-games.`}
      </p>
      <Link href="/models" className="inline-flex text-subhead font-medium text-primary hover:underline">
        Full evaluation
      </Link>
    </div>
  );
}

function FreshnessList({ datasets }: { datasets: DatasetStatus[] }) {
  return (
    <ul className="space-y-2.5">
      {datasets.map((d) => (
        <li key={d.dataset} className="flex items-center justify-between gap-3 text-subhead">
          <span>{DATASET_LABELS[d.dataset] ?? d.dataset}</span>
          <FreshnessBadge status={d.status} lastSync={d.last_successful_sync} />
        </li>
      ))}
    </ul>
  );
}

async function OverviewContent() {
  const result = await serverTry<Overview>("/overview");
  if (result.error) return <ApiErrorView error={result.error} />;
  const o = result.data;
  const today = o.upcoming.filter((g) => g.game_date === o.today);
  const initialDate = today.length ? o.today : (o.recent[0]?.game_date ?? o.today);
  const initialGames = today.length ? today : o.recent;
  const window =
    o.standouts.window_start && o.standouts.window_end
      ? `${formatGameDate(o.standouts.window_start)} – ${formatGameDate(o.standouts.window_end)}`
      : "Recent games";

  return (
    <div className="grid gap-5 lg:grid-cols-12">
      <Panel id="schedule" kicker="Schedule" title="Games" className="lg:col-span-7">
        <ScheduleBoard initialDate={initialDate} initialGames={initialGames} />
      </Panel>
      <Panel
        id="leaders"
        kicker={o.leaders?.season ?? "Leaders"}
        title="League leaders"
        className="lg:col-span-5"
      >
        {o.leaders ? (
          <LeadersBoard initial={o.leaders} />
        ) : (
          <Unavailable kind="empty" title="No season data yet" />
        )}
      </Panel>
      <Panel
        id="standouts"
        kicker={window}
        title="Standout performances"
        actions={
          <InfoHint term="Game Score">
            {o.standouts.criterion}. Game Score combines points, shooting efficiency, rebounds, assists,
            steals, blocks, fouls and turnovers into one number.
          </InfoHint>
        }
        className="lg:col-span-12"
      >
        <StandoutGrid standouts={o.standouts} />
      </Panel>
      <Panel id="model" kicker="Machine learning" title="Model accuracy" className="lg:col-span-7">
        <ModelPanel model={o.model} />
      </Panel>
      <Panel id="freshness" kicker="Data" title="Freshness" className="lg:col-span-5">
        <FreshnessList datasets={o.datasets} />
        <p className="mt-4 text-footnote text-muted-foreground">
          Synced from stats.nba.com on a schedule. Live in-game scores are not ingested.
        </p>
      </Panel>
    </div>
  );
}

export default function OverviewPage() {
  return (
    <>
      <PageHeader
        kicker="Command center"
        title="Overview"
        description="Today's games, the best recent performances, and how accurate the models are."
      />
      <Suspense fallback={<LoadingBlock label="Loading overview" className="panel p-5" />}>
        <OverviewContent />
      </Suspense>
    </>
  );
}
