import Link from "next/link";

import { CourtBackdrop } from "@/components/brand/court-backdrop";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { ApiErrorView } from "@/components/data/api-error";
import { CompareBar } from "@/components/data/compare-bar";
import { Panel } from "@/components/data/panel";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { PlayerProfile, PlayerSeasonStats, SeasonLine } from "@/lib/api/types";
import { formatPercent, formatStat } from "@/lib/format";
import { param, SEASON_LABEL, type SearchParams } from "@/lib/url";

import { ComparePicker, CompareTrend, type Picked, SeasonPicker } from "./compare-client";

const PLAYER_ID = /^\d{1,10}$/;
/** Without a season in the URL, start from the latest season where both have a meaningful sample. */
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
  const [profile, stats] = await Promise.all([
    serverTry<PlayerProfile>(`/players/${id}`),
    serverTry<PlayerSeasonStats>(`/players/${id}/stats`),
  ]);
  return { id, profile, stats };
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
    <section
      aria-labelledby="versus-title"
      className="relative overflow-hidden rounded-2xl border border-border bg-card"
    >
      <div
        aria-hidden
        className="absolute inset-0 opacity-30"
        style={{
          background: `linear-gradient(100deg, ${players[0].team?.primary_color ?? "transparent"} 0%, transparent 42%, transparent 58%, ${players[1].team?.primary_color ?? "transparent"} 100%)`,
        }}
      />
      <CourtBackdrop className="absolute inset-0 text-foreground/[0.06]" />
      <h2 id="versus-title" className="sr-only">
        {players[0].full_name} versus {players[1].full_name}, {season}
      </h2>
      <div className="relative grid grid-cols-2 items-center gap-4 p-5 sm:p-8 md:grid-cols-[1fr_auto_1fr]">
        {players.map((p, i) => (
          <div
            key={p.id}
            className={
              i === 1
                ? "flex flex-col items-center gap-3 text-center md:order-3"
                : "flex flex-col items-center gap-3 text-center"
            }
          >
            <PlayerCutout id={p.id} name={p.full_name} team={p.team} eager className="h-40 w-full sm:h-56" />
            <div>
              <Link
                href={`/players/${p.id}?season=${season}`}
                className="font-[family-name:var(--font-display)] text-[clamp(1.5rem,3.5vw,2.5rem)] leading-none font-extrabold uppercase hover:text-primary"
              >
                {p.full_name}
              </Link>
              <p className="text-footnote text-muted-foreground">
                {[p.team ? `${p.team.city} ${p.team.name}` : null, p.position].filter(Boolean).join(" · ")}
              </p>
            </div>
            <p className="text-subhead">
              <span className="numeral text-[2.75rem]">{i === 0 ? aLeads : bLeads}</span>
              <span className="block text-footnote text-muted-foreground">of {total} categories led</span>
            </p>
          </div>
        ))}
        <div className="order-last col-span-2 text-center md:order-2 md:col-span-1">
          <p className="numeral text-[3rem] text-muted-foreground">VS</p>
          <p className="kicker mt-1">{season} regular season</p>
          {ties > 0 && <p className="text-footnote text-muted-foreground">{ties} tied</p>}
        </div>
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

  const both = picked[0] && picked[1] ? ([picked[0], picked[1]] as [Picked, Picked]) : null;
  const statsError = sides.find((s) => s?.stats.error)?.stats.error;
  const seasonsOf = (i: number) => sides[i]?.stats.data?.seasons.map((l) => l.season) ?? [];
  const gamesIn = (i: number, s: string) =>
    sides[i]?.stats.data?.seasons.find((l) => l.season === s)?.games_played ?? 0;
  const common = both ? seasonsOf(0).filter((s) => seasonsOf(1).includes(s)) : [];
  const season =
    requested && SEASON_LABEL.test(requested) && common.includes(requested)
      ? requested
      : (common.find((c) => [0, 1].every((i) => gamesIn(i, c) >= MIN_DEFAULT_GAMES)) ?? common[0]);
  const lines =
    both && season
      ? ([0, 1].map((i) => sides[i]!.stats.data!.seasons.find((l) => l.season === season)!) as [
          SeasonLine,
          SeasonLine,
        ])
      : null;

  return (
    <div className="space-y-5">
      <ComparePicker players={picked} season={season} />
      {missing.length > 0 && (
        <Unavailable kind="empty" title="A player in this link wasn't found">
          No player has id {missing.join(" or ")}. Pick someone with the search above.
        </Unavailable>
      )}
      {!both ? (
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
            <div className="grid gap-8 lg:grid-cols-2">
              {GROUPS.map((group) => (
                <div key={group.title} className={group.title === "Per game" ? "lg:row-span-2" : undefined}>
                  <h3 className="kicker mb-3">{group.title}</h3>
                  <div className="grid grid-cols-2 pb-2 text-footnote font-medium">
                    <span className="truncate">{both[0].full_name}</span>
                    <span className="truncate text-right">{both[1].full_name}</span>
                  </div>
                  <div className="space-y-3">
                    {group.rows.map((row) => (
                      <CompareBar
                        key={row.label}
                        label={row.label}
                        left={row.value(lines[0]) ?? null}
                        right={row.value(lines[1]) ?? null}
                        format={row.format}
                        better={row.better}
                        names={[both[0].full_name, both[1].full_name]}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-footnote text-muted-foreground">
              Highlighted values lead the category; for turnovers lower is better. Minutes, games and
              double-doubles are context and aren&apos;t counted as leads. Shooting percentages are made over
              attempted for the whole season.
            </p>
          </Panel>
          <Panel id="form" kicker="Game by game" title="Form">
            <CompareTrend players={both} season={season} />
          </Panel>
        </>
      )}
    </div>
  );
}
