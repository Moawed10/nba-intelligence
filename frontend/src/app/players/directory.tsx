import Link from "next/link";

import { ApiErrorView } from "@/components/data/api-error";
import { FreshnessBadge } from "@/components/data/freshness-badge";
import { Pagination } from "@/components/data/pagination";
import { StateView } from "@/components/data/state-view";
import { serverTry } from "@/lib/api/server";
import type { PlayerPage, Team } from "@/lib/api/types";
import { hrefWith, oneOf, param, positiveInt, type SearchParams } from "@/lib/url";

import { DirectoryFilterBar, DirectoryTable } from "./directory-controls";
import { type DirectoryFilters, POSITIONS } from "./filters";

export const PAGE_SIZE = 25;

export function parseFilters(params: SearchParams): DirectoryFilters & { page: number } {
  const team = param(params, "team");
  const position = param(params, "position");
  return {
    team: team && /^\d+$/.test(team) ? team : undefined,
    position: oneOf(position, ["G", "F", "C", ""] as const, "") || undefined,
    status: param(params, "status") === "all" ? "all" : undefined,
    page: positiveInt(param(params, "page")),
  };
}

export async function Directory({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const { page, ...filters } = parseFilters(await searchParams);
  const [teams, players] = await Promise.all([
    serverTry<Team[]>("/teams"),
    serverTry<PlayerPage>("/players", {
      team_id: filters.team,
      position: filters.position,
      active: filters.status === "all" ? undefined : true,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
  ]);

  const filtered = Boolean(filters.team || filters.position || filters.status);
  const positionLabel = POSITIONS.find((p) => p.value === filters.position)?.label;
  const team = teams.data?.find((t) => String(t.id) === filters.team);
  const caption = [
    filters.status === "all" ? "All players" : "Active players",
    team && `${team.city} ${team.name}`,
    positionLabel,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section aria-labelledby="directory-heading" className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="directory-heading" className="text-title2 font-semibold">
          Directory
        </h2>
        {players.data && (
          <FreshnessBadge
            status={players.data.meta.data_freshness.status}
            lastSync={players.data.meta.data_freshness.last_successful_sync}
          />
        )}
      </div>
      {teams.data && <DirectoryFilterBar teams={teams.data} filters={filters} />}
      {players.error ? (
        <ApiErrorView error={players.error} />
      ) : players.data.items.length === 0 ? (
        <StateView
          kind="empty"
          title="No players match these filters"
          action={
            filtered ? (
              <Link
                href="/players"
                className="inline-flex min-h-10 items-center rounded-lg px-3 text-subhead font-medium text-primary hover:underline"
              >
                Clear filters
              </Link>
            ) : undefined
          }
        />
      ) : (
        <>
          <DirectoryTable players={players.data.items} caption={caption} />
          <Pagination
            label="Player directory pages"
            page={page}
            pages={Math.ceil(players.data.total / PAGE_SIZE)}
            total={players.data.total}
            href={(p) => hrefWith("/players", { ...filters }, { page: p === 1 ? undefined : p })}
          />
        </>
      )}
    </section>
  );
}
