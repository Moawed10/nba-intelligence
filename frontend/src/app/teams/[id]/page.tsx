import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache, Suspense } from "react";

import { TeamBand } from "@/components/brand/team-band";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { Panel } from "@/components/data/panel";
import { StatTile } from "@/components/data/stat-tile";
import { LoadingBlock } from "@/components/data/state-view";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { PlayerPage, TeamDetail, TeamSeasonStats } from "@/lib/api/types";
import { formatStat } from "@/lib/format";

import { RosterTable } from "./roster-table";

const TEAM_ID = /^\d{1,10}$/;
const ROSTER_LIMIT = 100;

const getTeam = cache((id: string) => serverTry<TeamDetail>(`/teams/${id}`));

export async function generateMetadata({ params }: PageProps<"/teams/[id]">): Promise<Metadata> {
  const { id } = await params;
  if (!TEAM_ID.test(id)) return { title: "Team not found" };
  const { data } = await getTeam(id);
  return { title: data ? `${data.team.city} ${data.team.name} · Teams` : "Teams" };
}

function TeamStats({ stats }: { stats: TeamSeasonStats }) {
  const pct = (value: number | null) => (value == null ? null : value * 100);
  return (
    <div className="space-y-4">
      <dl className="stat-grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6">
        <StatTile label="Points" value={stats.pts_per_game} footnote="Scored per game" />
        <StatTile label="Allowed" value={stats.opp_pts_per_game} footnote="Given up per game" />
        <StatTile label="Offense" value={stats.offensive_rating} footnote="Points per 100 possessions" />
        <StatTile label="Defense" value={stats.defensive_rating} footnote="Allowed per 100; lower is better" />
        <StatTile label="Net" value={stats.net_rating} footnote="Offense minus defense" />
        <StatTile label="Pace" value={stats.pace} footnote="Possessions per game" />
      </dl>
      <dl className="stat-grid grid-cols-3">
        <StatTile label="FG%" value={pct(stats.shooting.fg_pct)} unit="%" footnote="Field goals" />
        <StatTile label="3P%" value={pct(stats.shooting.fg3_pct)} unit="%" footnote="3-pointers" />
        <StatTile label="FT%" value={pct(stats.shooting.ft_pct)} unit="%" footnote="Free throws" />
      </dl>
    </div>
  );
}

async function TeamView({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!TEAM_ID.test(id)) notFound();
  const detail = await getTeam(id);
  if (detail.error?.status === 404) notFound();
  if (detail.error) return <ApiErrorView error={detail.error} />;

  const { team, season, record, roster, meta } = detail.data;
  const [stats, averages] = await Promise.all([
    serverTry<TeamSeasonStats>(`/teams/${id}/stats`, { season }),
    serverTry<PlayerPage>("/players", { team_id: id, season, sort: "-pts", limit: ROSTER_LIMIT }),
  ]);
  const bySeason = new Map((averages.data?.items ?? []).map((p) => [p.id, p.season_averages]));
  const players = roster.map((p) => ({ ...p, season_averages: bySeason.get(p.id) ?? null }));
  const freshness = meta.data_freshness;
  const name = `${team.city} ${team.name}`;

  return (
    <>
      <TeamBand team={team} ghost={team.name} labelledBy="team-name" className="-mt-6 md:-mt-8">
        <div className="flex flex-wrap items-center justify-between gap-x-10 gap-y-6 py-8 md:py-12">
          <div className="min-w-0">
            <p className="kicker">
              {team.conference} · {team.division} · {season} regular season
            </p>
            <h1 id="team-name" tabIndex={-1} className="display mt-4 text-[clamp(3.5rem,10vw,8.5rem)] outline-none">
              {name}
            </h1>
            <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-3 lg:gap-x-12">
              <div>
                <dd className="numeral text-[clamp(3.25rem,7vw,5.5rem)]">
                  {record.wins}–{record.losses}
                </dd>
                <dt className="kicker mt-1.5">Record</dt>
              </div>
              <div>
                <dd className="numeral text-[clamp(3.25rem,7vw,5.5rem)]">{formatStat(stats.data?.pts_per_game)}</dd>
                <dt className="kicker mt-1.5">Points per game</dt>
              </div>
            </dl>
          </div>
          <TeamMark team={team} size="xl" disc className="size-28 md:size-44" />
        </div>
      </TeamBand>
      <div className="space-y-14 pt-12 lg:pt-16">
        <Panel
          id="roster"
          kicker={`${season} regular season · per game`}
          title="Roster"
          actions={<FreshnessBadge status={freshness.status} lastSync={freshness.last_successful_sync} />}
        >
          {roster.length === 0 ? (
            <Unavailable kind="empty" title="No players are listed on this roster" />
          ) : (
            <>
              {averages.error && (
                <Unavailable kind="error" title="Player stats couldn't load" className="mb-4">
                  The roster is still listed below without its numbers.
                </Unavailable>
              )}
              <RosterTable players={players} caption={`${name} roster and ${season} per-game stats`} />
              <p className="mt-3 text-footnote text-muted-foreground">
                A dash means the player hasn&apos;t played a regular-season game this season.
              </p>
            </>
          )}
        </Panel>
        <Panel id="team-stats" kicker={`${season} regular season`} title="Team stats">
          {stats.error ? (
            <ApiErrorView error={stats.error} />
          ) : stats.data.games === 0 ? (
            <Unavailable kind="no_games" title={`No ${season} games played yet`} />
          ) : (
            <TeamStats stats={stats.data} />
          )}
        </Panel>
      </div>
    </>
  );
}

export default function TeamPage({ params }: PageProps<"/teams/[id]">) {
  return (
    <Suspense fallback={<LoadingBlock feature label="Loading team" />}>
      <TeamView params={params} />
    </Suspense>
  );
}
