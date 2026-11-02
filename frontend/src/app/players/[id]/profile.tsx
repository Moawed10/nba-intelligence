import { ArrowLeftRight, Target } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache, Suspense } from "react";

import { TeamBand } from "@/components/brand/team-band";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { ChartFrame } from "@/components/data/chart-frame";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatTile } from "@/components/data/stat-tile";
import { LoadingBlock, StateView } from "@/components/data/state-view";
import { Unavailable } from "@/components/data/unavailable";
import { serverPostTry, serverTry } from "@/lib/api/server";
import type {
  CareerLine,
  GameSummary,
  PlayerCareer,
  PlayerGameLine,
  PlayerGameLinePage,
  PlayerProfile,
  PlayerSeasonStats,
  PlayerTrends,
  SeasonLine,
  UpcomingForecast,
} from "@/lib/api/types";
import { formatGameDate, formatGameTime, formatGameValue, formatHeight, formatStat } from "@/lib/format";
import { hrefWith, oneOf, param, positiveInt, type SearchParams } from "@/lib/url";

import {
  CareerHistory,
  GameLogTable,
  ProfileControls,
  SplitsTable,
  TrendChart,
  TrendTable,
} from "./profile-client";
import { TREND_STAT_VALUES, TREND_STATS, type TrendStat } from "./stats";

export const LOG_PAGE_SIZE = 20;
const RECENT_GAMES = 5;
const NEXT_GAME_DAYS = 14;
const SECTION_TITLE = "headline text-[1.875rem]";
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
  const [profile, stats, career] = await Promise.all([
    getProfile(id),
    serverTry<PlayerSeasonStats>(`/players/${id}/stats`),
    serverTry<PlayerCareer>(`/players/${id}/career`),
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
        career={career.data?.regular.totals ?? null}
        freshness={<FreshnessBadge status={freshness.status} lastSync={freshness.last_successful_sync} />}
      />
      {stats.error ? (
        <ApiErrorView error={stats.error} />
      ) : !season ? (
        <div className="mt-10 space-y-10">
          {career.error ? (
            <ApiErrorView error={career.error} />
          ) : (
            career.data.regular.seasons.length + career.data.playoffs.seasons.length > 0 && (
              <CareerHistory career={career.data} name={data.player.full_name} />
            )
          )}
          <StateView
            kind="empty"
            title="No game-by-game stats for this player"
            message="Game logs, trends and splits start with the 2018-19 season. The career table above covers every season."
          />
        </div>
      ) : (
        <div className="space-y-14">
          <SectionNav
            sections={[
              ["averages-heading", "Averages"],
              ...(data.last_games.length ? ([["recent-heading", "Recent"]] as [string, string][]) : []),
              ...(data.player.is_active && data.player.team
                ? ([["next-heading", "Next game"]] as [string, string][])
                : []),
              ["trend-section", "Trend"],
              ["log-heading", "Game log"],
              ["career-heading", "Career"],
            ]}
          />
          <ProfileControls seasons={seasons} season={season} stat={stat} />
          <SeasonAverages line={stats.data.seasons.find((s) => s.season === season)!} />
          <RecentForm games={data.last_games} season={data.current_season} />
          {data.player.is_active && data.player.team && (
            <Suspense fallback={<LoadingBlock label="Loading next game" />}>
              <NextGame id={data.player.id} teamId={data.player.team.id} />
            </Suspense>
          )}
          <div id="trend-section">
            <Suspense key={`trend-${season}-${stat}`} fallback={<LoadingBlock label="Loading trend" />}>
              <Trends id={id} season={season} stat={stat} name={data.player.full_name} />
            </Suspense>
          </div>
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
          {career.error ? (
            <ApiErrorView error={career.error} />
          ) : (
            career.data.regular.seasons.length + career.data.playoffs.seasons.length > 0 && (
              <CareerHistory career={career.data} name={data.player.full_name} />
            )
          )}
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

function HeroLine({
  label,
  stats,
  games,
}: {
  label: string;
  stats: Record<string, number | null | undefined>;
  games: number;
}) {
  const size = "text-[clamp(3.75rem,8.5vw,7rem)]";
  return (
    <dl className="flex flex-wrap gap-x-8 gap-y-3 lg:gap-x-12" aria-label={label}>
      {HERO_STATS.map((s) => (
        <div key={s.key}>
          <dd className={`numeral ${size}`}>{formatStat(stats[s.key])}</dd>
          <dt className="kicker mt-1.5">{s.label}</dt>
        </div>
      ))}
      <div>
        <dd className={`numeral ${size}`}>{games}</dd>
        <dt className="kicker mt-1.5">GP</dt>
      </div>
    </dl>
  );
}

function ProfileHero({
  profile,
  line,
  career,
  freshness,
}: {
  profile: PlayerProfile;
  line: SeasonLine | null;
  /** Career regular-season averages, shown when there is no recent season. */
  career: CareerLine | null;
  freshness: React.ReactNode;
}) {
  const { player } = profile;
  const ghost = player.full_name.replace(/\s+(Jr\.?|Sr\.?|II|III|IV)$/, "").split(" ").at(-1);
  return (
    <TeamBand team={player.team} ghost={ghost} labelledBy="player-name" className="-mt-6 md:-mt-8">
      <div className="flex flex-col md:min-h-[34rem] md:justify-center">
        <div className="relative z-10 order-2 flex flex-col gap-7 py-8 md:max-w-[58%] md:py-12">
          <div>
            <p className="kicker flex items-center gap-2.5">
              {player.team && <TeamMark team={player.team} size="sm" disc />}
              {player.team
                ? `${player.team.city} ${player.team.name}`
                : player.is_active
                  ? "Free agent"
                  : "Former player"}
            </p>
            <h1 id="player-name" tabIndex={-1} className="display mt-5 text-[clamp(4rem,11vw,9.5rem)] outline-none">
              {player.full_name}
            </h1>
            <p className="mt-4 text-subhead font-medium">{identity(profile) || "Biography not available"}</p>
            <div className="mt-1.5 [&_*]:text-[color:var(--on)]">{freshness}</div>
          </div>
          {!line && career && (
            <HeroLine
              label="Career regular-season averages"
              stats={career.per_game}
              games={career.games}
            />
          )}
          {line && (
            <HeroLine
              label={`${line.season} regular-season averages`}
              stats={line.per_game}
              games={line.games_played}
            />
          )}
          <div className="flex flex-wrap gap-2">
            {player.is_active && (
              <Link href={`/predict?player=${player.id}`} className="btn btn-on-band">
                <Target aria-hidden className="size-4" />
                Predict next game
              </Link>
            )}
            <Link href={`/compare?p1=${player.id}`} className="btn btn-outline-band">
              <ArrowLeftRight aria-hidden className="size-4" />
              Compare
            </Link>
          </div>
        </div>
        <PlayerCutout
          id={player.id}
          name={player.full_name}
          team={player.team}
          eager
          plain
          className="order-1 mt-6 h-64 sm:h-80 md:absolute md:inset-y-0 md:right-0 md:mt-0 md:h-auto md:w-[50%] md:[&_img]:object-right-bottom"
        />
      </div>
    </TeamBand>
  );
}

/** Jump links to the dossier's sections; sticks under the top bar without covering what it scrolls to. */
function SectionNav({ sections }: { sections: [string, string][] }) {
  return (
    <nav
      aria-label="Sections of this profile"
      className="material-nav bleed sticky top-16 z-30 border-b border-border"
    >
      <ul className="scroll-quiet flex gap-1 overflow-x-auto">
        {sections.map(([id, label]) => (
          <li key={id} className="shrink-0">
            <a
              href={`#${id}`}
              className="flex min-h-11 items-center rounded-md px-2.5 text-subhead text-muted-foreground transition-colors duration-150 hover:text-foreground"
            >
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function SeasonAverages({ line }: { line: SeasonLine }) {
  const pct = (value: number | null) => (value == null ? null : value * 100);
  const noAttempts = (status: string | null) => (status === "no_attempts" ? "No attempts" : undefined);
  return (
    <section aria-labelledby="averages-heading" className="rule-top space-y-4 pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="averages-heading" className={SECTION_TITLE}>
          {line.season} regular season
        </h2>
        <p className="text-footnote text-muted-foreground">
          Per game · {line.games_played} {line.games_played === 1 ? "game" : "games"} played
        </p>
      </div>
      <dl className="stat-grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 max-lg:[&>*:last-child]:col-span-2">
        {TREND_STATS.map((s) => (
          <StatTile key={s.value} label={s.short} value={line.per_game[s.value]} footnote={s.label} />
        ))}
      </dl>
      <dl className="stat-grid grid-cols-2 sm:grid-cols-4">
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

/** The latest games on file, with their average set against the current season's. */
function RecentForm({
  games,
  season,
}: {
  games: PlayerGameLine[];
  season: PlayerProfile["current_season"];
}) {
  const recent = games.slice(0, RECENT_GAMES);
  if (recent.length === 0) return null;
  const average = (key: "pts" | "reb" | "ast") =>
    recent.reduce((sum, g) => sum + g.box[key], 0) / recent.length;
  return (
    <section aria-labelledby="recent-heading" className="rule-top space-y-4 pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="recent-heading" className={SECTION_TITLE}>
          Recent games
        </h2>
        <p className="text-footnote text-muted-foreground">
          Last {recent.length} {recent.length === 1 ? "game" : "games"} played · actual results
        </p>
      </div>
      <dl className="stat-grid grid-cols-3">
        {(["pts", "reb", "ast"] as const).map((key) => {
          const value = average(key);
          const baseline = season?.per_game[key];
          return (
            <StatTile
              key={key}
              label={`${key.toUpperCase()} average`}
              value={value}
              delta={baseline == null ? null : { value: value - baseline, versus: `${season!.season}` }}
            />
          );
        })}
      </dl>
      <ul className="scroll-quiet -mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-5 sm:px-0">
        {recent.map((g) => (
          <li key={g.game_id} className="w-36 shrink-0 sm:w-auto">
            <Link
              href={`/games/${g.game_id}`}
              className="block rounded-md bg-muted/60 p-3 transition-colors duration-150 hover:bg-muted"
            >
              <span className="flex items-center gap-1.5 text-footnote text-muted-foreground">
                <TeamMark team={g.opponent} size="xs" />
                {g.is_home ? "vs" : "@"} {g.opponent.abbreviation}
                {g.result && <span className="ml-auto font-semibold text-foreground">{g.result}</span>}
              </span>
              <span className="mt-2 block tabular-nums">
                <span className="numeral text-title1">{g.box.pts}</span>
                <span className="ml-1 text-footnote text-muted-foreground">pts</span>
              </span>
              <span className="block text-footnote text-muted-foreground tabular-nums">
                {g.box.reb} reb · {g.box.ast} ast · {formatGameDate(g.game_date)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The next scheduled game and, when one exists, its forecast; kept visibly apart from results. */
async function NextGame({ id, teamId }: { id: number; teamId: number }) {
  const upcoming = await serverTry<GameSummary[]>("/games/upcoming", { player_id: id, days: NEXT_GAME_DAYS });
  const game = upcoming.data?.[0];
  const forecasts = game
    ? await serverPostTry<UpcomingForecast[]>("/predictions/upcoming", { player_id: id, days: NEXT_GAME_DAYS })
    : null;
  const forecast = forecasts?.data?.find((f) => f.game.id === game?.id);
  const values = forecast?.prediction?.values.filter((v) => ["pts", "reb", "ast"].includes(v.stat)) ?? [];
  return (
    <section aria-labelledby="next-heading" className="rule-top space-y-4 pt-3">
      <h2 id="next-heading" className={SECTION_TITLE}>
        Next game
      </h2>
      {upcoming.error ? (
        <ApiErrorView error={upcoming.error} />
      ) : !game ? (
        <Unavailable kind="no_games" title={`No games in the next ${NEXT_GAME_DAYS} days`}>
          The published schedule shows nothing for this player&apos;s team in that window.
        </Unavailable>
      ) : (
        <div className="flex flex-wrap items-center gap-x-10 gap-y-4">
          <div className="flex min-w-0 items-center gap-3">
            <TeamMark team={game.home.team.id === teamId ? game.away.team : game.home.team} size="lg" />
            <div className="min-w-0">
              <p className="font-semibold">
                {game.home.team.id === teamId
                  ? `vs ${game.away.team.city} ${game.away.team.name}`
                  : `at ${game.home.team.city} ${game.home.team.name}`}
              </p>
              <p className="text-footnote text-muted-foreground">
                {game.tipoff_at ? formatGameTime(game.tipoff_at) : formatGameDate(game.game_date, true)}
              </p>
            </div>
          </div>
          {values.length > 0 && (
            <dl className="flex gap-6" aria-label="Forecast for this game">
              {values.map((v) => (
                <div key={v.stat}>
                  <dd className="numeral text-[3.25rem] text-primary">{formatStat(v.point)}</dd>
                  <dt className="kicker mt-0.5">Forecast {v.stat}</dt>
                </div>
              ))}
            </dl>
          )}
          <Link href={`/predict?player=${id}&game=${game.id}`} className="btn btn-secondary ml-auto max-sm:w-full">
            {values.length ? "See the full forecast" : "Open in Predictions"}
          </Link>
        </div>
      )}
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
    <details className="group panel">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-3 text-headline font-semibold transition-colors duration-150 hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
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
    <section aria-labelledby="log-heading" className="rule-top space-y-4 pt-3">
      <h2 id="log-heading" className={SECTION_TITLE}>
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
