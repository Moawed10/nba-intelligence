import Link from "next/link";

import { teamBandStyle } from "@/components/brand/team-band";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { TeamLink } from "@/components/brand/team-link";
import { ApiErrorView } from "@/components/data/api-error";
import { CompareBar } from "@/components/data/compare-bar";
import { Panel } from "@/components/data/panel";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { PlayerComparison, PlayerProfile, SeasonLine } from "@/lib/api/types";
import { formatPercent, formatStat } from "@/lib/format";
import { param, SEASON_LABEL, type SearchParams } from "@/lib/url";

import { ComparePicker, CompareTrend, PercentileRadar, type Picked, SeasonPicker } from "./compare-client";

const PLAYER_ID = /^\d{1,10}$/;
/** Without a season in the URL, the API opens on the latest season where both played this many. */
const MIN_DEFAULT_GAMES = 10;

interface Row {
  label: string;
  value: (s: SeasonLine) => number | null | undefined;
  format: (v: number | null) => string;
  better?: "higher" | "lower" | "neither";
  /** Counted toward "leads in N categories". */
  scored?: boolean;
}

const GROUPS: { title: string; rows: Row[] }[] = [
  {
    title: "Per game",
    rows: [
      { label: "Points", value: (s) => s.per_game.pts, format: formatStat, scored: true },
      { label: "Rebounds", value: (s) => s.per_game.reb, format: formatStat, scored: true },
      { label: "Assists", value: (s) => s.per_game.ast, format: formatStat, scored: true },
      { label: "3-pointers made", value: (s) => s.per_game.fg3m, format: formatStat, scored: true },
      { label: "Steals", value: (s) => s.per_game.stl, format: formatStat, scored: true },
      { label: "Blocks", value: (s) => s.per_game.blk, format: formatStat, scored: true },
      { label: "Turnovers", value: (s) => s.per_game.tov, format: formatStat, better: "lower", scored: true },
      { label: "Minutes", value: (s) => s.per_game.min, format: formatStat, better: "neither" },
    ],
  },
  {
    title: "Efficiency",
    rows: [
      { label: "Field goal %", value: (s) => s.shooting.fg_pct, format: formatPercent, scored: true },
      { label: "3-point %", value: (s) => s.shooting.fg3_pct, format: formatPercent, scored: true },
      { label: "Free throw %", value: (s) => s.shooting.ft_pct, format: formatPercent, scored: true },
      { label: "Effective FG %", value: (s) => s.efg_pct, format: formatPercent, scored: true },
      { label: "True shooting %", value: (s) => s.ts_pct, format: formatPercent, scored: true },
    ],
  },
  {
    title: "Availability",
    rows: [
      { label: "Games played", value: (s) => s.games_played, format: formatStat, better: "neither" },
      { label: "Double-doubles", value: (s) => s.double_doubles, format: formatStat, better: "neither" },
    ],
  },
];

function leadCounts(lines: [SeasonLine, SeasonLine]): [number, number, number] {
  const counts: [number, number, number] = [0, 0, 0];
  for (const row of GROUPS.flatMap((g) => g.rows).filter((r) => r.scored)) {
    const [a, b] = lines.map((l) => row.value(l));
    if (a == null || b == null) continue;
    if (a === b) counts[2] += 1;
    else if ((row.better === "lower") === a < b) counts[0] += 1;
    else counts[1] += 1;
  }
  return counts;
}

async function load(id: string | undefined) {
  if (!id) return null;
  return { id, profile: await serverTry<PlayerProfile>(`/players/${id}`) };
}

/** Both players in one season from GET /compare/players; an unshared season falls back to the default. */
async function comparison(p1: string, p2: string, season: string | undefined) {
  const result = await serverTry<PlayerComparison>("/compare/players", { p1, p2, season });
  if (season && result.error?.code === "no_common_season") {
    return serverTry<PlayerComparison>("/compare/players", { p1, p2 });
  }
  return result;
}

function toPicked(profile: PlayerProfile): Picked {
  const { id, full_name, team, position } = profile.player;
  return { id, full_name, team, position };
}

function Hero({
  players,
  lines,
  season,
}: {
  players: [Picked, Picked];
  lines: [SeasonLine, SeasonLine];
  season: string;
}) {
  const [aLeads, bLeads, ties] = leadCounts(lines);
  const total = aLeads + bLeads + ties;
  return (
    <section aria-labelledby="versus-title" className="bleed relative !px-0">
      <h2 id="versus-title" className="sr-only">
        {players[0].full_name} versus {players[1].full_name}, {season}
      </h2>
      <div className="grid grid-cols-2">
        {players.map((p, i) => (
          <div key={p.id} style={teamBandStyle(p.team)} className="team-band min-w-0 pt-5">
            <PlayerCutout id={p.id} name={p.full_name} team={p.team} eager plain className="h-40 w-full sm:h-72 lg:h-80" />
            <div className="p-4 text-center sm:p-6">
              {p.team && (
                <div className="mb-2">
                  <TeamLink team={p.team} size="md" />
                </div>
              )}
              <Link
                href={`/players/${p.id}?season=${season}`}
                className="display flex min-h-11 items-center justify-center text-[clamp(2rem,6vw,5rem)] underline-offset-4 hover:underline"
              >
                {p.full_name}
              </Link>
              <p className="mt-1 text-footnote font-medium">
                {[p.team ? `${p.team.city} ${p.team.name}` : null, p.position].filter(Boolean).join(" · ")}
              </p>
              <p className="mt-3">
                <span className="numeral text-[clamp(3.5rem,7vw,5.5rem)]">{i === 0 ? aLeads : bLeads}</span>
                <span className="block text-footnote font-medium">of {total} categories led</span>
              </p>
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-col items-center gap-1 border-b border-border py-3 text-center md:absolute md:top-6 md:left-1/2 md:-translate-x-1/2 md:rounded-full md:border md:bg-background md:px-6">
        <p aria-hidden className="numeral text-title1">VS</p>
        <p className="kicker">{season} regular season</p>
        {ties > 0 && <p className="text-footnote text-muted-foreground">{ties} tied</p>}
      </div>
    </section>
  );
}

export async function CompareView({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const query = await searchParams;
  const ids = [param(query, "p1"), param(query, "p2")].map((v) => (v && PLAYER_ID.test(v) ? v : undefined));
  const requested = param(query, "season");
  const sides = await Promise.all(ids.map(load));

  const failure = sides.find((s) => s?.profile.error && s.profile.error.status !== 404)?.profile.error;
  if (failure) return <ApiErrorView error={failure} />;
  const missing = sides.flatMap((s) => (s?.profile.error?.status === 404 ? [s.id] : []));
  const picked = sides.map((s) => (s?.profile.data ? toPicked(s.profile.data) : null)) as [
    Picked | null,
    Picked | null,
  ];

  const pair = picked[0] && picked[1] ? ([picked[0], picked[1]] as [Picked, Picked]) : null;
  const same = pair != null && pair[0].id === pair[1].id;
  const both = same ? null : pair;
  const compared = both
    ? await comparison(ids[0]!, ids[1]!, requested && SEASON_LABEL.test(requested) ? requested : undefined)
    : null;
  const statsError = compared?.error ?? null;
  const data = compared?.data ?? null;
  const common = data?.common_seasons ?? [];
  const season = data?.season ?? undefined;
  const lines = data?.season ? (data.lines as [SeasonLine, SeasonLine]) : null;

  return (
    <div className="space-y-10">
      <ComparePicker players={picked} season={season} />
      {missing.length > 0 && (
        <Unavailable kind="empty" title="A player in this link wasn't found">
          No player has id {missing.join(" or ")}. Pick someone with the search above.
        </Unavailable>
      )}
      {same ? (
        <Unavailable kind="empty" title="Pick two different players">
          Both slots hold {pair![0].full_name}. Swap one of them using the search above.
        </Unavailable>
      ) : !both ? (
        <Unavailable
          kind="empty"
          title={picked[0] || picked[1] ? "Pick a second player" : "Pick two players"}
        >
          Search by name. The comparison opens on the latest regular season in which both played at least{" "}
          {MIN_DEFAULT_GAMES} games, and the link can be shared.
        </Unavailable>
      ) : statsError ? (
        <ApiErrorView error={statsError} />
      ) : !lines || !season ? (
        <Unavailable kind="no_games" title="These players never played in the same season">
          Season averages are only compared within one regular season, so the numbers mean the same thing.
        </Unavailable>
      ) : (
        <>
          <Hero players={both} lines={lines} season={season} />
          <Panel
            id="head-to-head"
            kicker={`${season} regular season`}
            title="Head to head"
            actions={<SeasonPicker players={[both[0].id, both[1].id]} seasons={common} season={season} />}
          >
            <div className="grid gap-x-12 gap-y-8 lg:grid-cols-2">
              {GROUPS.map((group) => (
                <div key={group.title} className={group.title === "Per game" ? "lg:row-span-2" : undefined}>
                  <h3 className="kicker mb-3">{group.title}</h3>
                  <div className="grid grid-cols-2 gap-3 border-b border-border pb-2 text-footnote font-medium">
                    <span className="flex items-center gap-1.5">
                      <span aria-hidden className="size-2 shrink-0 rounded-full bg-chart-1" />
                      {both[0].full_name}
                    </span>
                    <span className="flex items-center justify-end gap-1.5 text-right">
                      {both[1].full_name}
                      <span aria-hidden className="size-2 shrink-0 rotate-45 bg-chart-2" />
                    </span>
                  </div>
                  <div className="divide-y divide-border/60">
                    {group.rows.map((row) => (
                      <div key={row.label} className="py-2.5">
                        <CompareBar
                          label={row.label}
                          left={row.value(lines[0]) ?? null}
                          right={row.value(lines[1]) ?? null}
                          format={row.format}
                          better={row.better}
                          names={[both[0].full_name, both[1].full_name]}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-footnote text-muted-foreground">
              The brighter value with a marker leads the category; for turnovers lower is better. Minutes, games and
              double-doubles are context and aren&apos;t counted as leads. Shooting percentages are made over
              attempted for the whole season.
            </p>
          </Panel>
          <Panel id="ranking" kicker={`${season} regular season`} title="Strengths">
            <PercentileRadar
              players={both}
              axes={data!.axes}
              qualification={data!.qualification}
              qualified={data!.qualified}
            />
          </Panel>
          <Panel id="form" kicker="Game by game" title="Form">
            <CompareTrend players={both} season={season} />
          </Panel>
        </>
      )}
    </div>
  );
}
