import Link from "next/link";
import { cache, Suspense } from "react";

import { CourtBackdrop } from "@/components/brand/court-backdrop";
import { TeamBand } from "@/components/brand/team-band";
import { TeamLink } from "@/components/brand/team-link";
import { PlayerAvatar } from "@/components/brand/player-avatar";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { GameTicker } from "@/components/data/game-ticker";
import { LiveRefresh } from "@/components/data/live-refresh";
import { InfoHint } from "@/components/data/info-hint";
import { PageHeader } from "@/components/data/page-header";
import { Panel } from "@/components/data/panel";
import { Numeral } from "@/components/data/numeral";
import { PlayerFinder } from "./players/player-finder";
import { Unavailable } from "@/components/data/unavailable";
import { Skeleton } from "@/components/ui/skeleton";
import { serverTry } from "@/lib/api/server";
import type { DatasetStatus, GameSummary, ModelSnapshot, Overview, Performance, Standouts } from "@/lib/api/types";
import { formatGameDate, formatGameTime, formatPercent, formatStat, milestoneLabel } from "@/lib/format";
import { isLive, liveLabel } from "@/lib/live";
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
  career_history: "Career history",
};

/** Shared by the header's date and the page body within one request. */
const getOverview = cache(() => serverTry<Overview>("/overview"));

/** Editorial ranking: rule-separated entries led by the rank, with the box score as the payoff. */
function StandoutGrid({ standouts }: { standouts: Standouts }) {
  if (standouts.performances.length === 0) {
    return (
      <Unavailable kind="empty" title="No completed games yet">
        Standout lines appear after the first final box scores.
      </Unavailable>
    );
  }
  return (
    <ol className="stagger grid gap-x-10 md:grid-cols-2">
      {standouts.performances.map((p, index) => {
        const line = [
          ["PTS", p.box.pts],
          ["REB", p.box.reb],
          ["AST", p.box.ast],
          ["FG", `${p.box.fgm}–${p.box.fga}`],
        ] as const;
        return (
          <li key={`${p.game_id}-${p.player_id}`} className="border-b border-border">
            <Link
              href={`/players/${p.player_id}`}
              className="group flex h-full gap-4 py-4 transition-colors duration-150"
            >
              <span aria-hidden className="numeral w-8 shrink-0 text-[2.5rem] text-muted-foreground/70">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 space-y-3">
                <span className="flex items-center gap-3">
                  <PlayerAvatar id={p.player_id} name={p.full_name} team={p.team} size="lg" square />
                  <span className="min-w-0 flex-1">
                    <span className="display block text-[1.875rem] transition-colors duration-150 group-hover:text-primary">
                      <span className="sr-only">Number {index + 1}: </span>
                      {p.full_name}
                    </span>
                    <span className="mt-0.5 block text-footnote text-muted-foreground">
                      {p.team.abbreviation} {p.is_home ? "vs" : "@"} {p.opponent.abbreviation} ·{" "}
                      {formatGameDate(p.game_date)}
                      {p.result && ` · ${p.result}`}
                    </span>
                  </span>
                </span>
                <span className="grid grid-cols-4 gap-2">
                  {line.map(([label, value]) => (
                    <span key={label}>
                      <span className="numeral block text-title1">{value}</span>
                      <span className="kicker mt-0.5 block">{label}</span>
                    </span>
                  ))}
                </span>
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-footnote text-muted-foreground">
                  <span>Game Score {formatStat(p.game_score)}</span>
                  {milestoneLabel(p.box) && (
                    <span className="font-medium text-foreground">{milestoneLabel(p.box)}</span>
                  )}
                </span>
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
        Accuracy appears here after the first training run is evaluated on a season it never saw.
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
          Average miss per statistic for the model and a simple average, {model.test_season}
        </caption>
        <thead className="text-footnote text-muted-foreground">
          <tr className="border-b border-border">
            <th scope="col" className="py-1.5 text-left font-medium">
              Statistic
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              Model miss
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              Simple average miss
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
        Miss is how far off a prediction is per game, on average. The simple average predicts each player&apos;s
        average over their previous 10 games.
        {doubleDouble?.brier != null &&
          ` Double-double probability: Brier score ${doubleDouble.brier.toFixed(3)} over ${doubleDouble.n.toLocaleString("en-US")} player-games.`}
      </p>
      <Link href="/models" className="inline-flex min-h-11 items-center text-subhead font-medium text-primary hover:underline">
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

const HERO_NUMBER = "text-[clamp(3.75rem,9vw,7.5rem)]";

function lastName(fullName: string): string {
  return fullName.replace(/\s+(Jr\.?|Sr\.?|II|III|IV)$/, "").split(" ").at(-1) ?? fullName;
}

function StandoutHero({ p, window }: { p: Performance; window: string }) {
  const line = [
    { label: "Points", value: p.box.pts },
    { label: "Rebounds", value: p.box.reb },
    { label: "Assists", value: p.box.ast },
  ];
  return (
    <TeamBand team={p.team} ghost={lastName(p.full_name)} labelledBy="hero-title">
      <div className="flex flex-col md:min-h-[34rem] md:justify-center">
        <div className="relative z-10 order-2 flex flex-col gap-7 py-8 md:max-w-[58%] md:py-12">
          <div>
            <p className="kicker flex items-center gap-2.5">
              <TeamLink team={p.team} size="md" />
              Performance of the week · {window}
            </p>
            <h2 id="hero-title" className="display mt-5 text-[clamp(4rem,11vw,9.5rem)]">
              <Link href={`/players/${p.player_id}`} className="underline-offset-8 hover:underline">
                {p.full_name}
              </Link>
            </h2>
            <p className="mt-4 text-subhead font-medium">
              {p.team.city} {p.team.name} {p.is_home ? "vs" : "at"} {p.opponent.city} {p.opponent.name} ·{" "}
              {formatGameDate(p.game_date, true)}
              {p.result && ` · ${p.result === "W" ? "Win" : "Loss"}`}
            </p>
          </div>
          <dl className="flex flex-wrap gap-x-8 gap-y-4 lg:gap-x-12">
            {line.map((s) => (
              <div key={s.label}>
                <dd>
                  <Numeral value={s.value} className={HERO_NUMBER} />
                </dd>
                <dt className="kicker mt-1.5">{s.label}</dt>
              </div>
            ))}
            <div>
              <dd>
                <Numeral value={p.game_score} decimals={1} className={HERO_NUMBER} />
              </dd>
              <dt className="kicker mt-1.5 flex h-[1lh] items-center gap-1">
                Game Score
                <InfoHint term="Game Score">
                  A single-number summary of a box score: points, shooting efficiency, rebounds, assists,
                  steals, blocks, fouls and turnovers.
                </InfoHint>
              </dt>
            </div>
          </dl>
          <p className="font-mono text-footnote tabular-nums">
            {p.box.fgm}–{p.box.fga} FG · {p.box.fg3m}–{p.box.fg3a} 3PT · {p.box.ftm}–{p.box.fta} FT ·{" "}
            {Math.round(p.minutes)} min
            {milestoneLabel(p.box) && ` · ${milestoneLabel(p.box)}`}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href={`/players/${p.player_id}`} className="btn btn-on-band">
              Player profile
            </Link>
            <Link href={`/games/${p.game_id}`} className="btn btn-outline-band">
              Game page
            </Link>
          </div>
        </div>
        <PlayerCutout
          id={p.player_id}
          name={p.full_name}
          team={p.team}
          eager
          plain
          className="order-1 mt-6 h-64 sm:h-80 md:absolute md:inset-y-0 md:right-0 md:mt-0 md:h-auto md:w-[50%] md:[&_img]:object-right-bottom"
        />
      </div>
    </TeamBand>
  );
}

/** Without a standout line yet, the next or latest game takes the feature spot. */
function MatchupFeature({ game }: { game: GameSummary }) {
  const status =
    game.status === "final"
      ? "Final"
      : isLive(game)
        ? liveLabel(game)
        : game.tipoff_at
          ? formatGameTime(game.tipoff_at)
          : formatGameDate(game.game_date, true);
  const showScore = game.away.score != null && game.home.score != null;
  return (
    <section aria-labelledby="hero-title" className="stage p-5 sm:p-8 lg:p-10">
      <CourtBackdrop className="-z-10" />
      <p className="kicker text-primary">{status}</p>
      <h2 id="hero-title" className="display mt-3 text-[clamp(2.5rem,7vw,5.5rem)]">
        <Link href={`/games/${game.id}`} className="transition-colors duration-150 hover:text-primary">
          {game.away.team.name} at {game.home.team.name}
        </Link>
      </h2>
      <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-4">
        {[game.away, game.home].map((side) => (
          <div key={side.team.id} className="flex items-center gap-3">
            <TeamMark team={side.team} size="xl" className="max-sm:size-14" />
            {showScore && <span className="numeral text-[clamp(3rem,7vw,5rem)]">{side.score}</span>}
          </div>
        ))}
      </div>
    </section>
  );
}

async function OverviewDate() {
  const { data } = await getOverview();
  return data ? formatGameDate(data.today, true) : "Today";
}

async function OverviewContent() {
  const result = await getOverview();
  if (result.error) return <ApiErrorView error={result.error} />;
  const o = result.data;
  const today = [...o.live, ...o.upcoming].filter((g) => g.game_date === o.today);
  const initialDate = today.length ? o.today : (o.recent[0]?.game_date ?? o.today);
  const initialGames = today.length ? today : o.recent;
  const window =
    o.standouts.window_start && o.standouts.window_end
      ? `${formatGameDate(o.standouts.window_start)} – ${formatGameDate(o.standouts.window_end)}`
      : "Recent games";

  const top = o.standouts.performances[0];
  const tickerGames = [...o.live, ...o.recent, ...o.upcoming];
  const featuredGame = o.live[0] ?? initialGames[0];

  return (
    <div className="min-w-0">
      <LiveRefresh games={tickerGames} />
      <GameTicker games={tickerGames} label="Recent and upcoming games" />
      {top ? (
        <StandoutHero p={top} window={window} />
      ) : (
        featuredGame && <MatchupFeature game={featuredGame} />
      )}
      <div className="space-y-14 pt-12 lg:space-y-20 lg:pt-16">
        <Panel id="schedule" kicker="Schedule" title="Games">
          <ScheduleBoard initialDate={initialDate} initialGames={initialGames} />
        </Panel>
        <div className="grid gap-14 lg:grid-cols-12 lg:gap-12">
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
            className="lg:col-span-8"
          >
            <StandoutGrid standouts={o.standouts} />
          </Panel>
          <Panel
            id="leaders"
            kicker={o.leaders?.season ?? "Leaders"}
            title="League leaders"
            className="self-start lg:sticky lg:top-24 lg:col-span-4"
          >
            {o.leaders ? (
              <LeadersBoard initial={o.leaders} />
            ) : (
              <Unavailable kind="empty" title="No season data yet" />
            )}
          </Panel>
        </div>
        <div className="band-alt bleed grid gap-10 py-10 lg:grid-cols-12 lg:gap-12">
          <section aria-labelledby="model-title" className="min-w-0 lg:col-span-7">
            <p className="kicker mb-1">Behind the numbers</p>
            <h2 id="model-title" className="headline mb-4 text-title1">
              Model accuracy
            </h2>
            <ModelPanel model={o.model} />
          </section>
          <section aria-labelledby="freshness-title" className="min-w-0 lg:col-span-5">
            <p className="kicker mb-1">Data</p>
            <h2 id="freshness-title" className="headline mb-4 text-title1">
              Freshness
            </h2>
            <FreshnessList datasets={o.datasets} />
            <p className="mt-4 text-footnote text-muted-foreground">
              Synced from stats.nba.com on a schedule. Scores update live while a game is on.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div role="status" aria-live="polite" className="space-y-6 lg:space-y-8">
      <span className="sr-only">Loading overview</span>
      <Skeleton className="h-12 w-full rounded-md" />
      <Skeleton className="h-[34rem] w-full rounded-2xl md:h-[30rem]" />
      <div className="grid gap-6 lg:grid-cols-12 lg:gap-8">
        <Skeleton className="h-96 rounded-xl lg:col-span-7" />
        <Skeleton className="h-96 rounded-xl lg:col-span-5" />
      </div>
    </div>
  );
}

export default function OverviewPage() {
  return (
    <>
      <PageHeader
        compact
        kicker={
          <Suspense fallback="Today">
            <OverviewDate />
          </Suspense>
        }
        title="Overview"
        actions={<PlayerFinder compact />}
      />
      <Suspense fallback={<OverviewSkeleton />}>
        <OverviewContent />
      </Suspense>
    </>
  );
}
