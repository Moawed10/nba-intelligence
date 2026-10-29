import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { CompareBar } from "@/components/data/compare-bar";
import { PageHeader } from "@/components/data/page-header";
import { Panel } from "@/components/data/panel";
import { LoadingBlock } from "@/components/data/state-view";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { HistoricSeason, Team, TeamHistory } from "@/lib/api/types";
import { formatPercent, formatStat } from "@/lib/format";
import { param, type SearchParams } from "@/lib/url";

import { CompareTabs } from "../compare-tabs";
import { type Slot, TeamPickers } from "./team-pickers";

export const metadata: Metadata = { title: "Compare teams" };

const TEAM_ID = /^\d{1,10}$/;

const EXAMPLES = [
  {
    label: "1995-96 Bulls vs 2015-16 Warriors",
    href: "/compare/teams?t1=1610612741&s1=1995-96&t2=1610612744&s2=2015-16",
  },
  {
    label: "1985-86 Celtics vs 1986-87 Lakers",
    href: "/compare/teams?t1=1610612738&s1=1985-86&t2=1610612747&s2=1986-87",
  },
  {
    label: "1978-79 SuperSonics vs 2011-12 Thunder",
    href: "/compare/teams?t1=1610612760&s1=1978-79&t2=1610612760&s2=2011-12",
  },
];

interface Row {
  label: string;
  value: (s: HistoricSeason) => number | null | undefined;
  format: (v: number | null) => string;
  better?: "higher" | "lower" | "neither";
}

const GROUPS: { title: string; rows: Row[] }[] = [
  {
    title: "Per game",
    rows: [
      { label: "Points", value: (s) => s.per_game.pts, format: formatStat },
      { label: "Rebounds", value: (s) => s.per_game.reb, format: formatStat },
      { label: "Assists", value: (s) => s.per_game.ast, format: formatStat },
      { label: "Steals", value: (s) => s.per_game.stl, format: formatStat },
      { label: "Blocks", value: (s) => s.per_game.blk, format: formatStat },
      { label: "3-pointers made", value: (s) => s.per_game.fg3m, format: formatStat },
      { label: "Turnovers", value: (s) => s.per_game.tov, format: formatStat, better: "lower" },
    ],
  },
  {
    title: "Shooting",
    rows: [
      { label: "Field goal %", value: (s) => s.fg_pct, format: formatPercent },
      { label: "3-point %", value: (s) => s.fg3_pct, format: formatPercent },
      { label: "Free throw %", value: (s) => s.ft_pct, format: formatPercent },
    ],
  },
  {
    title: "Efficiency",
    rows: [
      { label: "Offensive rating", value: (s) => s.off_rating, format: formatStat },
      { label: "Defensive rating", value: (s) => s.def_rating, format: formatStat, better: "lower" },
      { label: "Net rating", value: (s) => s.net_rating, format: formatStat },
      { label: "Pace", value: (s) => s.pace, format: formatStat, better: "neither" },
    ],
  },
];

function outcome(s: HistoricSeason): string {
  if (s.finals === "champion") return "Won the championship";
  if (s.finals === "finals") return "Reached the Finals";
  if (s.playoff_wins || s.playoff_losses) return `Playoffs ${s.playoff_wins}–${s.playoff_losses}`;
  return "Missed the playoffs";
}

function TeamCard({ history, season }: { history: TeamHistory; season: HistoricSeason }) {
  const sameIdentity = season.city === history.team.city && season.name === history.team.name;
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      {sameIdentity ? (
        <TeamMark team={history.team} size="xl" />
      ) : (
        <span
          aria-hidden
          className="inline-flex size-20 items-center justify-center rounded-2xl bg-muted text-title3 font-semibold text-muted-foreground"
        >
          {season.season.slice(2, 4)}
        </span>
      )}
      <div>
        <p className="kicker">{season.season}</p>
        <p className="text-title3 font-semibold">
          {season.city} {season.name}
        </p>
        <p className="text-subhead">
          <span className="font-semibold tabular-nums">
            {season.wins}–{season.losses}
          </span>{" "}
          <span className="text-muted-foreground">· {outcome(season)}</span>
        </p>
      </div>
    </div>
  );
}

async function slotFor(teamId: string | undefined, season: string | undefined) {
  if (!teamId || !TEAM_ID.test(teamId)) return { history: null, chosen: null, error: null };
  const result = await serverTry<TeamHistory>(`/teams/${teamId}/history`);
  if (result.error)
    return { history: null, chosen: null, error: result.error.status === 404 ? null : result.error };
  const chosen = result.data.seasons.find((s) => s.season === season) ?? result.data.seasons[0] ?? null;
  return { history: result.data, chosen, error: null };
}

async function TeamCompareView({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const query = await searchParams;
  const [teams, a, b] = await Promise.all([
    serverTry<Team[]>("/teams"),
    slotFor(param(query, "t1"), param(query, "s1")),
    slotFor(param(query, "t2"), param(query, "s2")),
  ]);
  const failure = teams.error ?? a.error ?? b.error;
  if (failure) return <ApiErrorView error={failure} />;

  const franchises = [...teams.data!]
    .sort((x, y) => `${x.city} ${x.name}`.localeCompare(`${y.city} ${y.name}`))
    .map((t) => ({ id: t.id, label: `${t.city} ${t.name}` }));
  const slots = [a, b].map((s): Slot => ({
    teamId: s.history?.team.id ?? null,
    season: s.chosen?.season ?? null,
    seasons: (s.history?.seasons ?? []).map((x) => ({
      season: x.season,
      label: `${x.season} · ${x.city} ${x.name}`,
    })),
  })) as [Slot, Slot];

  const both = a.chosen && b.chosen && a.history && b.history;
  return (
    <div className="space-y-5">
      <TeamPickers franchises={franchises} slots={slots} />
      {!both ? (
        <Unavailable kind="empty" title="Pick two team-seasons">
          Any franchise, any season since 1946-47, under the name it had that year. Try{" "}
          {EXAMPLES.map((e, i) => (
            <span key={e.href}>
              {i > 0 && (i === EXAMPLES.length - 1 ? " or " : ", ")}
              <Link href={e.href} className="font-medium text-primary hover:underline">
                {e.label}
              </Link>
            </span>
          ))}
          .
        </Unavailable>
      ) : (
        <>
          <section aria-labelledby="team-versus" className="panel relative overflow-hidden">
            <h2 id="team-versus" className="sr-only">
              {a.chosen!.season} {a.chosen!.city} {a.chosen!.name} versus {b.chosen!.season} {b.chosen!.city}{" "}
              {b.chosen!.name}
            </h2>
            <div className="grid grid-cols-2 items-center gap-4 p-5 sm:p-8 md:grid-cols-[1fr_auto_1fr]">
              <TeamCard history={a.history!} season={a.chosen!} />
              <p className="order-last col-span-2 text-center text-title2 font-semibold text-muted-foreground md:order-none md:col-span-1">
                vs
              </p>
              <TeamCard history={b.history!} season={b.chosen!} />
            </div>
          </section>
          <Panel id="team-head-to-head" kicker="Regular season" title="Side by side">
            <div className="grid gap-8 lg:grid-cols-2">
              {GROUPS.map((group) => (
                <div key={group.title} className={group.title === "Per game" ? "lg:row-span-2" : undefined}>
                  <h3 className="kicker mb-3">{group.title}</h3>
                  <div className="space-y-3">
                    {group.rows.map((row) => (
                      <CompareBar
                        key={row.label}
                        label={row.label}
                        left={row.value(a.chosen!) ?? null}
                        right={row.value(b.chosen!) ?? null}
                        format={row.format}
                        better={row.better}
                        names={[
                          `${a.chosen!.season} ${a.chosen!.name}`,
                          `${b.chosen!.season} ${b.chosen!.name}`,
                        ]}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-footnote text-muted-foreground">
              — means the league did not record it that season: turnovers and offensive rebounds before
              1973-74, 3-pointers in this source before 1982-83, pace and ratings before 1996-97. Per-game
              numbers are as played and not adjusted for each era&apos;s pace. Ratings are points per 100
              possessions; a lower defensive rating is better.
            </p>
          </Panel>
        </>
      )}
    </div>
  );
}

export default function CompareTeamsPage({ searchParams }: PageProps<"/compare/teams">) {
  return (
    <>
      <PageHeader
        kicker="Head to head"
        title="Compare teams"
        description="Any two team-seasons in league history, side by side."
      />
      <CompareTabs current="/compare/teams" />
      <Suspense fallback={<LoadingBlock label="Loading teams" className="panel p-5" />}>
        <TeamCompareView searchParams={searchParams} />
      </Suspense>
    </>
  );
}
