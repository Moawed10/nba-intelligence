"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useId, useOptimistic, useTransition } from "react";

import { type Column, DataTable } from "@/components/data/data-table";
import type { PlayerSummary, Team } from "@/lib/api/types";
import { hrefWith } from "@/lib/url";

import { type DirectoryFilters, POSITIONS } from "./filters";

const SELECT =
  "h-11 w-full rounded-xl border border-input bg-card px-3 text-body outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function DirectoryFilterBar({ teams, filters }: { teams: Team[]; filters: DirectoryFilters }) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();
  // Controls reflect the choice immediately while the server renders the new results.
  const [shown, setShown] = useOptimistic(filters);
  const id = useId();

  function update(updates: Partial<DirectoryFilters>) {
    startTransition(() => {
      setShown({ ...shown, ...updates });
      router.push(hrefWith(pathname, { ...shown }, { ...updates, page: undefined }), { scroll: false });
    });
  }

  return (
    <form
      aria-label="Filter players"
      aria-busy={pending}
      onSubmit={(event) => event.preventDefault()}
      className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
    >
      <div>
        <label htmlFor={`${id}-team`} className="mb-1.5 block text-subhead font-medium">
          Team
        </label>
        <select
          id={`${id}-team`}
          value={shown.team ?? ""}
          onChange={(event) => update({ team: event.target.value || undefined })}
          className={SELECT}
        >
          <option value="">All teams</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.city} {team.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-position`} className="mb-1.5 block text-subhead font-medium">
          Position
        </label>
        <select
          id={`${id}-position`}
          value={shown.position ?? ""}
          onChange={(event) => update({ position: event.target.value || undefined })}
          className={SELECT}
        >
          <option value="">All positions</option>
          {POSITIONS.map((position) => (
            <option key={position.value} value={position.value}>
              {position.label}
            </option>
          ))}
        </select>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-subhead">
        <input
          type="checkbox"
          checked={shown.status === "all"}
          onChange={(event) => update({ status: event.target.checked ? "all" : undefined })}
          className="size-5 accent-primary"
        />
        Include former players
      </label>
      <p role="status" className="sr-only">
        {pending ? "Updating players…" : ""}
      </p>
    </form>
  );
}

function seasons(player: PlayerSummary): string {
  if (player.from_year == null) return "—";
  return player.to_year == null || player.to_year === player.from_year
    ? String(player.from_year)
    : `${player.from_year}–${player.to_year}`;
}

const COLUMNS: Column<PlayerSummary>[] = [
  {
    key: "name",
    header: "Player",
    cell: (p) => (
      <Link
        href={`/players/${p.id}`}
        className="inline-flex min-h-8 items-center font-medium text-foreground hover:text-primary hover:underline"
      >
        {p.full_name}
      </Link>
    ),
  },
  {
    key: "team",
    header: "Team",
    cell: (p) => (p.team ? <abbr title={`${p.team.city} ${p.team.name}`}>{p.team.abbreviation}</abbr> : "—"),
  },
  { key: "position", header: "Pos", description: "Position", cell: (p) => p.position ?? "—" },
  { key: "years", header: "Years", description: "First and last NBA season", cell: seasons, numeric: true },
];

export function DirectoryTable({ players, caption }: { players: PlayerSummary[]; caption: string }) {
  return <DataTable caption={caption} columns={COLUMNS} rows={players} rowKey={(p) => String(p.id)} />;
}
