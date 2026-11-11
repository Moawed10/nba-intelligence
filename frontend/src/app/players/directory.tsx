import { ArrowDown, ArrowUp } from "lucide-react";
import Link from "next/link";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { teamBandStyle } from "@/components/brand/team-band";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { Pagination } from "@/components/data/pagination";
import { Panel } from "@/components/data/panel";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { DataStatus, DirectoryPlayer, PlayerPage, Team } from "@/lib/api/types";
import { formatShooting, formatStat, playerTeamLabel } from "@/lib/format";
import { hrefWith, type SearchParams } from "@/lib/url";
import { cn } from "@/lib/utils";

import { DirectoryFilterBar } from "./directory-controls";
import {
  ALL_TIME,
  type DirectoryState,
  includesFormer,
  parseDirectory,
  isShooting,
  POSITIONS,
  SHOOTING_COLUMNS as SHOOTING,
  SORT_COLUMNS,
} from "./filters";

export const PAGE_SIZE = 25;
const MOBILE_STATS = ["pts", "reb", "ast", "min"] as const;
type Column = (typeof SORT_COLUMNS)[number] | (typeof SHOOTING)[number];

/** A season shows per-game averages; all time shows career totals, which is how all-time
 * leaders are counted. Shooting percentages are the same either way. */
function statValue(player: DirectoryPlayer, key: Column["key"], allTime: boolean): string {
  if (isShooting(key)) return formatShooting(player.season_averages?.[key] ?? null);
  if (allTime) {
    const t = player.totals;
    const value = key === "games" ? t?.games_played : t?.[key];
    return value == null ? "—" : value.toLocaleString("en-US");
  }
  const a = player.season_averages;
  return key === "games" ? String(a?.games_played ?? "—") : formatStat(a?.[key] ?? null);
}

function describe(column: Column, allTime: boolean): string {
  if (!allTime || isShooting(column.key)) return column.description;
  return column.key === "games"
    ? "Games played"
    : `Total ${column.description.replace(/ per game$/, "").toLowerCase()}`;
}

function filtersOf(state: DirectoryState) {
  const { season, team, position, status, sort } = state;
  return { season, team, position, status, sort };
}

function SortHeader({ state, column }: { state: DirectoryState; column: Column }) {
  const description = describe(column, state.season === ALL_TIME);
  const active = state.sortKey === column.key;
  const next = active && state.descending ? column.key : `-${column.key}`;
  const Icon = active ? (state.descending ? ArrowDown : ArrowUp) : null;
  return (
    <th
      scope="col"
      aria-sort={active ? (state.descending ? "descending" : "ascending") : undefined}
      className="px-2 py-2.5 text-right last:pr-4"
    >
      <Link
        href={hrefWith("/players", filtersOf(state), {
          sort: next === "-pts" ? undefined : next,
          page: undefined,
        })}
        scroll={false}
        title={description}
        className={cn(
          "inline-flex min-h-8 items-center justify-end gap-1 rounded-md px-1 font-medium transition-colors hover:text-foreground",
          active ? "text-primary" : "text-muted-foreground",
        )}
      >
        {column.label}
        <span className="sr-only">, {description}, sort</span>
        {Icon && <Icon aria-hidden className="size-3.5" />}
      </Link>
    </th>
  );
}

function PlayerCell({ player }: { player: DirectoryPlayer }) {
  return (
    <div className="flex items-center gap-3">
      <PlayerAvatar id={player.id} name={player.full_name} team={player.team} size="md" />
      <div className="min-w-0">
        <Link
          href={`/players/${player.id}`}
          className="block truncate font-medium text-foreground after:absolute after:inset-0 hover:text-primary"
        >
          {player.full_name}
        </Link>
        <p className="flex items-center gap-1.5 text-footnote text-muted-foreground">
          {player.jersey_number && <span className="tabular-nums">#{player.jersey_number}</span>}
          {player.team ? (
            <>
              <TeamMark team={player.team} size="xs" className="size-4 rounded text-[0.4375rem]" />
              {player.team.abbreviation}
            </>
          ) : (
            playerTeamLabel(player)
          )}
          {player.position && <span>· {player.position}</span>}
        </p>
      </div>
    </div>
  );
}

function DirectoryTable({
  players,
  state,
  caption,
}: {
  players: DirectoryPlayer[];
  state: DirectoryState;
  caption: string;
}) {
  return (
    <>
      <div
        role="region"
        aria-label={caption}
        tabIndex={0}
        className="scroll-quiet hidden overflow-x-auto md:block"
      >
        <table className="w-full border-collapse text-subhead">
          <caption className="sr-only">{caption}</caption>
          <thead className="text-footnote">
            <tr className="border-b border-border">
              <th scope="col" className="px-5 py-2.5 text-left font-medium text-muted-foreground">
                Player
              </th>
              {SORT_COLUMNS.map((column) => (
                <SortHeader key={column.key} state={state} column={column} />
              ))}
              {SHOOTING.map((column) => (
                <SortHeader key={column.key} state={state} column={column} />
              ))}
            </tr>
          </thead>
          <tbody>
            {players.map((player) => {
              const allTime = state.season === ALL_TIME;
              return (
                <tr
                  key={player.id}
                  className="relative border-b border-border/60 transition-colors last:border-0 focus-within:bg-muted/60 hover:bg-muted/60"
                >
                  <th scope="row" className="py-2 pl-5 text-left font-normal">
                    <PlayerCell player={player} />
                  </th>
                  {[...SORT_COLUMNS, ...SHOOTING].map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-3 py-2 text-right tabular-nums last:pr-5",
                        state.sortKey === column.key
                          ? "numeral text-headline text-foreground"
                          : "text-muted-foreground",
                      )}
                    >
                      {statValue(player, column.key, allTime)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul aria-label={caption} className="divide-y divide-border/60 md:hidden">
        {players.map((player) => (
          <li key={player.id} className="relative py-3">
            <PlayerCell player={player} />
            <dl className="mt-2 grid grid-cols-4 gap-2 pl-13 text-center">
              {MOBILE_STATS.map((key) => (
                <div key={key}>
                  <dt className="kicker">{key.toUpperCase()}</dt>
                  <dd className={cn("tabular-nums", state.sortKey === key && "font-semibold text-primary")}>
                    {statValue(player, key, state.season === ALL_TIME)}
                  </dd>
                </div>
              ))}
              {SHOOTING.map(({ key, label }) => (
                <div key={key}>
                  <dt className="kicker">{label}</dt>
                  <dd className={cn("tabular-nums", state.sortKey === key && "font-semibold text-primary")}>
                    {formatShooting(player.season_averages?.[key] ?? null)}
                  </dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}

function Podium({
  players,
  column,
  allTime,
}: {
  players: DirectoryPlayer[];
  column: Column;
  allTime: boolean;
}) {
  return (
    <section aria-labelledby="podium-title" className="border-b border-border py-5">
      <h3 id="podium-title" className="kicker mb-3">
        Top 3 · {describe(column, allTime)}
      </h3>
      <ol className="stagger grid gap-3 sm:grid-cols-3">
        {players.map((p, i) => (
          <li key={p.id}>
            <Link
              href={`/players/${p.id}`}
              className="group relative flex h-full flex-col overflow-hidden rounded-lg border border-border transition-colors duration-150 hover:bg-muted"
            >
              <div style={teamBandStyle(p.team)} className="team-band pt-3">
                <PlayerCutout
                  id={p.id}
                  name={p.full_name}
                  team={p.team}
                  eager={i === 0}
                  plain
                  className="h-36 sm:h-44"
                />
              </div>
              <span className="flex items-end justify-between gap-3 p-4 pt-3">
                <span className="min-w-0">
                  <span className="kicker block text-primary">#{i + 1}</span>
                  <span className="display mt-0.5 block text-title2 transition-colors duration-150 group-hover:text-primary">
                    {p.full_name}
                  </span>
                  <span className="block text-footnote text-muted-foreground">
                    {playerTeamLabel(p)}
                    {p.position ? ` · ${p.position}` : ""}
                  </span>
                </span>
                <span className="text-right">
                  <span className="numeral block text-[2.75rem]">{statValue(p, column.key, allTime)}</span>
                  <span className="kicker">{column.label}</span>
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

export async function Directory({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const state = parseDirectory(await searchParams);
  const [teams, status] = await Promise.all([
    serverTry<Team[]>("/teams"),
    serverTry<DataStatus>("/data-status"),
  ]);
  const seasons = (status.data?.seasons ?? []).filter((s) => s.final_games > 0).map((s) => s.season);
  const allTime = state.season === ALL_TIME;
  const season = allTime || (state.season && seasons.includes(state.season)) ? state.season : seasons[0];
  const players = season
    ? await serverTry<PlayerPage>("/players", {
        season,
        team_id: state.team,
        position: state.position,
        active: includesFormer(state) ? undefined : true,
        sort: `${state.descending ? "-" : ""}${state.sortKey}`,
        limit: PAGE_SIZE,
        offset: (state.page - 1) * PAGE_SIZE,
      })
    : null;

  const team = teams.data?.find((t) => String(t.id) === state.team);
  const positionLabel = POSITIONS.find((p) => p.value === state.position)?.label;
  const sortColumn = [...SORT_COLUMNS, ...SHOOTING].find((c) => c.key === state.sortKey);
  const sortLabel = sortColumn?.description ?? "Name";
  const scope = allTime ? "All-time regular season" : `${season} regular season`;
  const caption = [
    scope,
    team && (allTime ? `with the ${team.city} ${team.name}` : `${team.city} ${team.name}`),
    positionLabel,
    `sorted by ${(allTime && sortColumn ? describe(sortColumn, true) : sortLabel).toLowerCase()}`,
  ]
    .filter(Boolean)
    .join(" · ");
  const filtered = Boolean(state.team || state.position || state.status);
  const freshness = players?.data?.meta.data_freshness;

  let body;
  if (status.error) body = <ApiErrorView error={status.error} />;
  else if (!players)
    body = (
      <Unavailable kind="empty" title="No completed games are stored yet">
        The directory fills in once the first box scores are ingested.
      </Unavailable>
    );
  else if (players.error) body = <ApiErrorView error={players.error} />;
  else if (players.data.items.length === 0)
    body = (
      <Unavailable
        kind="empty"
        title="No players match these filters"
        action={
          filtered && (
            <Link href="/players" className="text-subhead font-medium text-primary hover:underline">
              Clear filters
            </Link>
          )
        }
      >
        {allTime
          ? "Only players whose careers are on record are listed."
          : `Only players with regular-season games in ${season} are listed.`}
      </Unavailable>
    );

  return (
    <Panel
      id="directory"
      kicker={season ? scope : "Directory"}
      title="Player directory"
      actions={
        freshness && <FreshnessBadge status={freshness.status} lastSync={freshness.last_successful_sync} />
      }
    >
      {teams.data && seasons.length > 0 && (
        <div className="border-b border-border pb-4">
          <DirectoryFilterBar teams={teams.data} seasons={seasons} filters={filtersOf(state)} />
          {allTime && (
            <p className="mt-3 max-w-prose text-footnote text-muted-foreground">
              Career regular-season totals as the NBA publishes them, updated daily.
              {team ? ` Only seasons played for the ${team.name} count.` : ""} Steals and blocks were first
              counted in 1973-74 and 3-pointers in 1979-80. Many former players&rsquo; careers are still being
              loaded, so some all-time greats are not listed yet.
            </p>
          )}
        </div>
      )}
      {body ? (
        <div className="pt-4">{body}</div>
      ) : (
        players?.data && (
          <>
            {state.page === 1 && state.descending && sortColumn && players.data.items.length >= 3 && (
              <Podium players={players.data.items.slice(0, 3)} column={sortColumn} allTime={allTime} />
            )}
            {isShooting(state.sortKey) && (
              <p className="pt-4 text-footnote text-muted-foreground">
                {allTime
                  ? "Percentages rank only players who reached the NBA's career minimums: 2,000 made field goals (also used for TS%), 250 made 3-pointers or 1,200 made free throws."
                  : "Percentages rank only players on pace for the NBA's full-season minimums: 300 made field goals (also used for TS%), 82 made 3-pointers or 125 made free throws."}{" "}
                Everyone else is listed after them.
              </p>
            )}
            <div>
              <DirectoryTable players={players.data.items} state={{ ...state, season }} caption={caption} />
            </div>
            <div className="pb-3">
              <Pagination
                label="Player directory pages"
                page={state.page}
                pages={Math.ceil(players.data.total / PAGE_SIZE)}
                total={players.data.total}
                href={(p) => hrefWith("/players", filtersOf(state), { page: p === 1 ? undefined : p })}
              />
            </div>
          </>
        )
      )}
    </Panel>
  );
}
