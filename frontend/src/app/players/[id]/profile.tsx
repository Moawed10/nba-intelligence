import { ArrowLeftRight, Target } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache, Suspense } from "react";

import { CourtBackdrop } from "@/components/brand/court-backdrop";
import { PlayerAvatar } from "@/components/brand/player-avatar";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { ChartFrame } from "@/components/data/chart-frame";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatTile } from "@/components/data/stat-tile";
import { LoadingBlock, StateView } from "@/components/data/state-view";
import { serverTry } from "@/lib/api/server";
import type {
  PlayerGameLinePage,
  PlayerProfile,
  PlayerSeasonStats,
  PlayerTrends,
  SeasonLine,
} from "@/lib/api/types";
import { formatGameDate, formatGameValue, formatHeight, formatStat } from "@/lib/format";
import { hrefWith, oneOf, param, positiveInt, type SearchParams } from "@/lib/url";

import { GameLogTable, ProfileControls, SplitsTable, TrendChart, TrendTable } from "./profile-client";
import { TREND_STAT_VALUES, TREND_STATS, type TrendStat } from "./stats";

export const LOG_PAGE_SIZE = 20;
const PLAYER_ID = /^\d{1,10}$/;

/** Deduplicated per request: generateMetadata and the page both read the profile. */
export const getProfile = cache((id: string) => serverTry<PlayerProfile>(`/players/${id}`));

function identity({ player }: PlayerProfile): string {
  const team = player.team
    ? `${player.team.city} ${player.team.name}`
    : player.is_active
      ? null
      : "Former player";
  const body = [
    player.height_inches ? formatHeight(player.height_inches) : null,
    player.weight_lbs ? `${player.weight_lbs} lb` : null,
  ]
    .filter(Boolean)
    .join(", ");
  return [team, player.position, body].filter(Boolean).join(" · ");
}

export async function PlayerProfileView({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { id } = await params;
  if (!PLAYER_ID.test(id)) notFound();
  const query = await searchParams;
  const [profile, stats] = await Promise.all([
    getProfile(id),
    serverTry<PlayerSeasonStats>(`/players/${id}/stats`),
  ]);
  if (profile.error?.status === 404) notFound();
  if (profile.error) {
    return (
      <>
        <PageHeader title="Player" />
        <ApiErrorView error={profile.error} />
      </>
    );
  }

  const data = profile.data;
  const freshness = data.meta.data_freshness;
  const seasons = stats.data?.seasons.map((s) => s.season) ?? [];
  const requested = param(query, "season");
  const season = requested && seasons.includes(requested) ? requested : seasons[0];
  const stat = oneOf(param(query, "stat"), TREND_STAT_VALUES, "pts");
  const logPage = positiveInt(param(query, "log"));

  return (
    <>
      <ProfileHero
        profile={data}
        line={stats.data?.seasons.find((s) => s.season === season) ?? null}
        freshness={<FreshnessBadge status={freshness.status} lastSync={freshness.last_successful_sync} />}
      />
      {stats.error ? (
        <ApiErrorView error={stats.error} />
      ) : !season ? (
        <StateView
          kind="empty"
          title="No regular-season games in our data"
          message="NBA Intelligence stores box scores from the 2018-19 season onward."
        />
      ) : (
        <div className="mt-8 space-y-8">
          <ProfileControls seasons={seasons} season={season} stat={stat} />
          <SeasonAverages line={stats.data.seasons.find((s) => s.season === season)!} />
          <Suspense key={`trend-${season}-${stat}`} fallback={<LoadingBlock label="Loading trend" />}>
            <Trends id={id} season={season} stat={stat} name={data.player.full_name} />
          </Suspense>
          <Suspense key={`splits-${season}`} fallback={<LoadingBlock label="Loading splits" />}>
            <Splits
              id={id}
              season={season}
              preloaded={stats.data.splits_season === season ? stats.data : null}
            />
          </Suspense>
          <Suspense key={`log-${season}-${logPage}`} fallback={<LoadingBlock label="Loading game log" />}>
            <GameLog
              id={id}
              season={season}
              stat={stat}
              page={logPage}
              explicitSeason={requested === season}
            />
          </Suspense>
        </div>
      )}
    </>
  );
}

const HERO_STATS = [
  { key: "pts", label: "PTS" },
  { key: "reb", label: "REB" },
  { key: "ast", label: "AST" },
] as const;

function ProfileHero({
  profile,
  line,
  freshness,
}: {
  profile: PlayerProfile;
  line: SeasonLine | null;
  freshness: React.ReactNode;
}) {
  const { player } = profile;
  const color = player.team?.primary_color ?? null;
  return (
    <section
      aria-labelledby="player-name"
      className="relative overflow-hidden rounded-2xl border border-border bg-card"
      style={
        color
          ? {
              backgroundImage: `linear-gradient(115deg, color-mix(in oklab, ${color} 30%, var(--card)) 0%, var(--card) 62%)`,
            }
          : undefined
      }
    >
      <CourtBackdrop color={color} />
      <div className="relative flex flex-col gap-6 p-5 sm:p-7 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-center gap-4 sm:gap-5">
          <PlayerAvatar
            id={player.id}
            name={player.full_name}
            team={player.team}
            size="xl"
            className="max-sm:size-16 max-sm:text-lg"
          />
          <div className="min-w-0">
            <p className="kicker flex items-center gap-2">
              {player.team && <TeamMark team={player.team} size="xs" />}
              {player.team
                ? `${player.team.city} ${player.team.name}`
                : player.is_active
                  ? "Free agent"
                  : "Former player"}
            </p>
            <h1
              id="player-name"
              tabIndex={-1}
              className="mt-1 text-[2rem] leading-tight font-bold tracking-tight outline-none sm:text-display"
            >
              {player.full_name}
            </h1>
            <p className="mt-1 text-subhead text-muted-foreground">
              {identity(profile) || "Biography not available"}
            </p>
            <div className="mt-2">{freshness}</div>
          </div>
        </div>
        <div className="flex flex-col gap-4 lg:items-end">
          {line && (
            <dl className="flex gap-6 sm:gap-8" aria-label={`${line.season} regular-season averages`}>
              {HERO_STATS.map((s) => (
                <div key={s.key}>
                  <dt className="kicker">{s.label}</dt>
                  <dd className="text-[2.25rem] leading-none font-semibold tracking-tight tabular-nums sm:text-[2.75rem]">
                    {formatStat(line.per_game[s.key])}
                  </dd>
                </div>
              ))}
              <div>
                <dt className="kicker">GP</dt>
                <dd className="text-[2.25rem] leading-none font-semibold tracking-tight text-muted-foreground tabular-nums sm:text-[2.75rem]">
                  {line.games_played}
                </dd>
              </div>
            </dl>
          )}
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/predict?player=${player.id}`}
              className="inline-flex h-10 items-center gap-2 rounded-full bg-primary px-4 text-subhead font-semibold text-primary-foreground transition-transform hover:brightness-110 active:scale-[0.98]"
            >
              <Target aria-hidden className="size-4" />
              Predict next game
            </Link>
            <Link
              href={`/compare?p1=${player.id}`}
              className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-card/70 px-4 text-subhead font-medium transition-colors hover:border-foreground/25 active:scale-[0.98]"
            >
              <ArrowLeftRight aria-hidden className="size-4" />
              Compare
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function SeasonAverages({ line }: { line: SeasonLine }) {
  const pct = (value: number | null) => (value == null ? null : value * 100);
  const noAttempts = (status: string | null) => (status === "no_attempts" ? "No attempts" : undefined);
  return (
    <section aria-labelledby="averages-heading" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="averages-heading" className="text-title2 font-semibold">
          {line.season} regular season
        </h2>
        <p className="text-footnote text-muted-foreground">
          Per game · {line.games_played} {line.games_played === 1 ? "game" : "games"} played
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {TREND_STATS.map((s) => (
          <StatTile key={s.value} label={s.short} value={line.per_game[s.value]} footnote={s.label} />
        ))}
      </dl>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          label="FG%"
          value={pct(line.shooting.fg_pct)}
          unit="%"
          footnote={noAttempts(line.shooting.fg_pct_status) ?? `${line.totals.fgm}–${line.totals.fga}`}
        />
        <StatTile
          label="3P%"
          value={pct(line.shooting.fg3_pct)}
          unit="%"
          footnote={noAttempts(line.shooting.fg3_pct_status) ?? `${line.totals.fg3m}–${line.totals.fg3a}`}
        />
        <StatTile
          label="FT%"
          value={pct(line.shooting.ft_pct)}
          unit="%"
          footnote={noAttempts(line.shooting.ft_pct_status) ?? `${line.totals.ftm}–${line.totals.fta}`}
        />
        <StatTile label="TS%" value={pct(line.ts_pct)} unit="%" footnote="True shooting" />
      </dl>
    </section>
  );
}

async function Trends({
  id,
  season,
  stat,
  name,
}: {
  id: string;
  season: string;
  stat: TrendStat;
  name: string;
}) {
  const result = await serverTry<PlayerTrends>(`/players/${id}/trends`, { stat, season });
  const label = TREND_STATS.find((s) => s.value === stat)!.label;
  const title = `${label} by game`;
  if (result.error) return <ApiErrorView error={result.error} />;
  const { points, average, games_played } = result.data;
  if (points.length === 0) {
    return <StateView kind="empty" title={`No games played in ${season}`} />;
  }
  const best = points.reduce((top, p) => (p.value > top.value ? p : top), points[0]);
  const summary =
    `${name} averaged ${formatStat(average)} ${label.toLowerCase()} over ${games_played} games in ${season}. ` +
    `Season high: ${formatGameValue(best.value)} ${best.is_home ? "vs" : "at"} ${best.opponent_abbreviation} on ` +
    `${formatGameDate(best.game_date, true)}.`;
  return (
    <ChartFrame
      title={title}
      unit={`${label} per game, ${season}, including playoffs`}
      summary={summary}
      chart={<TrendChart points={points} statLabel={label} />}
      table={<TrendTable points={points} caption={`${title}, ${season}`} />}
    />
  );
}

async function Splits({
  id,
  season,
  preloaded,
}: {
  id: string;
  season: string;
  preloaded: PlayerSeasonStats | null;
}) {
  const result = preloaded
    ? { data: preloaded, error: null }
    : await serverTry<PlayerSeasonStats>(`/players/${id}/stats`, { season });
  if (result.error) return <ApiErrorView error={result.error} />;
  if (result.data.splits.length === 0) return null;
  return (
    <details className="group rounded-xl bg-card">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-3 text-headline font-semibold [&::-webkit-details-marker]:hidden">
        Home, away and rest splits
        <span aria-hidden className="text-muted-foreground transition-transform group-open:rotate-90">
          ›
        </span>
      </summary>
      <div className="px-1 pb-2">
        <p className="px-3 pb-3 text-footnote text-muted-foreground">
          {season} regular season. Rest counts days off since the player&apos;s previous game.
        </p>
        <SplitsTable splits={result.data.splits} caption={`Splits, ${season} regular season`} />
      </div>
    </details>
  );
}

async function GameLog({
  id,
  season,
  stat,
  page,
  explicitSeason,
}: {
  id: string;
  season: string;
  stat: TrendStat;
  page: number;
  explicitSeason: boolean;
}) {
  const result = await serverTry<PlayerGameLinePage>(`/players/${id}/games`, {
    season,
    limit: LOG_PAGE_SIZE,
    offset: (page - 1) * LOG_PAGE_SIZE,
  });
  return (
    <section aria-labelledby="log-heading" className="space-y-3">
      <h2 id="log-heading" className="text-title2 font-semibold">
        Game log
      </h2>
      {result.error ? (
        <ApiErrorView error={result.error} />
      ) : result.data.items.length === 0 ? (
        <StateView kind="empty" title={`No games on this page of the ${season} log`} />
      ) : (
        <>
          <GameLogTable games={result.data.items} caption={`Game log, ${season}, most recent first`} />
          <Pagination
            label="Game log pages"
            page={page}
            pages={Math.ceil(result.data.total / LOG_PAGE_SIZE)}
            total={result.data.total}
            href={(p) =>
              hrefWith(
                `/players/${id}`,
                { season: explicitSeason ? season : undefined, stat: stat === "pts" ? undefined : stat },
                { log: p === 1 ? undefined : p },
              )
            }
          />
        </>
      )}
    </section>
  );
}
