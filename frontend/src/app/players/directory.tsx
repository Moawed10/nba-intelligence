import { ArrowDown, ArrowUp } from "lucide-react";
import Link from "next/link";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { Pagination } from "@/components/data/pagination";
import { Panel } from "@/components/data/panel";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type { DataStatus, DirectoryPlayer, PlayerPage, Team } from "@/lib/api/types";
import { formatPercent, formatStat } from "@/lib/format";
import { hrefWith, type SearchParams } from "@/lib/url";
import { cn } from "@/lib/utils";

import { DirectoryFilterBar } from "./directory-controls";
import { type DirectoryState, parseDirectory, POSITIONS, SORT_COLUMNS } from "./filters";

export const PAGE_SIZE = 25;
const MOBILE_STATS = ["pts", "reb", "ast", "min"] as const;

function filtersOf(state: DirectoryState) {
  const { season, team, position, status, sort } = state;
  return { season, team, position, status, sort };
}

function SortHeader({ state, column }: { state: DirectoryState; column: (typeof SORT_COLUMNS)[number] }) {
  const active = state.sortKey === column.key;
  const next = active && state.descending ? column.key : `-${column.key}`;
  const Icon = active ? (state.descending ? ArrowDown : ArrowUp) : null;
  return (
    <th
      scope="col"
      aria-sort={active ? (state.descending ? "descending" : "ascending") : undefined}
      className="px-2 py-2.5 text-right"
    >
      <Link
        href={hrefWith("/players", filtersOf(state), {
          sort: next === "-pts" ? undefined : next,
          page: undefined,
        })}
        scroll={false}
        title={column.description}
        className={cn(
          "inline-flex min-h-8 items-center justify-end gap-1 rounded-md px-1 font-medium transition-colors hover:text-foreground",
          active ? "text-primary" : "text-muted-foreground",
        )}
      >
        {column.label}
        <span className="sr-only">, {column.description}, sort</span>
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
          {player.team ? (
            <>
              <TeamMark team={player.team} size="xs" className="size-4 rounded text-[0.4375rem]" />
              {player.team.abbreviation}
            </>
          ) : (
            "No current team"
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
      <div className="hidden md:block">
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
              <th scope="col" className="px-5 py-2.5 text-right font-medium text-muted-foreground">
                <abbr title="Field-goal percentage" className="no-underline">
                  FG%
                </abbr>
              </th>
            </tr>
          </thead>
          <tbody>
            {players.map((player) => {
              const a = player.season_averages;
              return (
                <tr
                  key={player.id}
                  className="relative border-b border-border/60 transition-colors last:border-0 focus-within:bg-muted/60 hover:bg-muted/60"
                >
                  <th scope="row" className="py-2 pl-5 text-left font-normal">
                    <PlayerCell player={player} />
                  </th>
                  {SORT_COLUMNS.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-3 py-2 text-right tabular-nums",
                        state.sortKey === column.key
                          ? "numeral text-headline text-foreground"
                          : "text-muted-foreground",
                      )}
                    >
                      {column.key === "games"
                        ? (a?.games_played ?? "—")
                        : formatStat(a?.[column.key] ?? null)}
                    </td>
                  ))}
                  <td className="px-5 py-2 text-right text-muted-foreground tabular-nums">
                    {formatPercent(a?.fg_pct ?? null)}
                  </td>
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
                    {formatStat(player.season_averages?.[key] ?? null)}
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

function Podium({ players, column }: { players: DirectoryPlayer[]; column: (typeof SORT_COLUMNS)[number] }) {
  const value = (p: DirectoryPlayer) =>
    column.key === "games" ? p.season_averages?.games_played : p.season_averages?.[column.key];
  return (
    <section aria-labelledby="podium-title" className="border-b border-border px-4 py-5 sm:px-5">
      <h3 id="podium-title" className="kicker mb-3">
        Top 3 · {column.description}
      </h3>
      <ol className="stagger grid gap-3 sm:grid-cols-3">
        {players.map((p, i) => (
          <li key={p.id}>
            <Link
              href={`/players/${p.id}`}
              className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-background/40 transition-colors hover:border-foreground/25"
            >
              <PlayerCutout
                id={p.id}
                name={p.full_name}
                team={p.team}
                eager={i === 0}
                className="h-36 sm:h-40"
              />
              <span className="flex items-end justify-between gap-3 p-4 pt-3">
                <span className="min-w-0">
                  <span className="kicker block text-primary">#{i + 1}</span>
                  <span className="block truncate font-[family-name:var(--font-display)] text-title2 leading-tight font-extrabold uppercase group-hover:text-primary">
                    {p.full_name}
                  </span>
                  <span className="block text-footnote text-muted-foreground">
                    {p.team?.abbreviation ?? "No current team"}
                    {p.position ? ` · ${p.position}` : ""}
                  </span>
                </span>
                <span className="text-right">
                  <span className="numeral block text-[2.75rem]">
                    {column.key === "games" ? (value(p) ?? "—") : formatStat(value(p) ?? null)}
                  </span>
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
  const season = state.season && seasons.includes(state.season) ? state.season : seasons[0];
  const players = season
    ? await serverTry<PlayerPage>("/players", {
        season,
        team_id: state.team,
        position: state.position,
        active: state.status === "all" ? undefined : true,
        sort: `${state.descending ? "-" : ""}${state.sortKey}`,
        limit: PAGE_SIZE,
        offset: (state.page - 1) * PAGE_SIZE,
      })
    : null;

  const team = teams.data?.find((t) => String(t.id) === state.team);
  const positionLabel = POSITIONS.find((p) => p.value === state.position)?.label;
  const sortColumn = SORT_COLUMNS.find((c) => c.key === state.sortKey);
  const sortLabel = sortColumn?.description ?? "Name";
  const caption = [
    `${season} regular season`,
    team && `${team.city} ${team.name}`,
    positionLabel,
    `sorted by ${sortLabel.toLowerCase()}`,
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
        Only players with regular-season games in {season} are listed.
      </Unavailable>
    );

  return (
    <Panel
      id="directory"
      kicker={season ? `${season} regular season` : "Directory"}
      title="Player directory"
      actions={
        freshness && <FreshnessBadge status={freshness.status} lastSync={freshness.last_successful_sync} />
      }
      bodyClassName="p-0 sm:p-0"
    >
      {teams.data && seasons.length > 0 && (
        <div className="border-b border-border px-4 py-4 sm:px-5">
          <DirectoryFilterBar teams={teams.data} seasons={seasons} filters={filtersOf(state)} />
        </div>
      )}
      {body ? (
        <div className="p-4 sm:p-5">{body}</div>
      ) : (
        players?.data && (
          <>
            {state.page === 1 && state.descending && sortColumn && players.data.items.length >= 3 && (
              <Podium players={players.data.items.slice(0, 3)} column={sortColumn} />
            )}
            <div className="px-4 md:px-0">
              <DirectoryTable players={players.data.items} state={{ ...state, season }} caption={caption} />
            </div>
            <div className="px-4 pb-3 sm:px-5">
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
