"use client";

import { usePathname, useRouter } from "next/navigation";
import { useId, useOptimistic, useTransition } from "react";

import { SegmentedControl } from "@/components/data/segmented-control";
import type { Team } from "@/lib/api/types";
import { hrefWith } from "@/lib/url";
import { cn } from "@/lib/utils";

import { type DirectoryFilters, POSITIONS } from "./filters";

const SELECT = "field w-full";

export function DirectoryFilterBar({
  teams,
  seasons,
  filters,
}: {
  teams: Team[];
  seasons: string[];
  filters: DirectoryFilters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();
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
      className={cn(
        "grid gap-3 transition-opacity sm:grid-cols-2 lg:grid-cols-[9rem_minmax(0,14rem)_auto_1fr] lg:items-end",
        pending && "opacity-70",
      )}
    >
      <div>
        <label htmlFor={`${id}-season`} className="kicker mb-1.5 block">
          Season
        </label>
        <select
          id={`${id}-season`}
          value={shown.season ?? seasons[0]}
          onChange={(event) =>
            update({ season: event.target.value === seasons[0] ? undefined : event.target.value })
          }
          className={SELECT}
        >
          {seasons.map((season) => (
            <option key={season} value={season}>
              {season}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-team`} className="kicker mb-1.5 block">
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
      <div className="min-w-0">
        <span className="kicker mb-1.5 block" aria-hidden>
          Position
        </span>
        <SegmentedControl
          className="max-w-full overflow-x-auto"
          label="Position"
          value={shown.position ?? "all"}
          onChange={(value) => update({ position: value === "all" ? undefined : value })}
          segments={[
            { value: "all", label: "All" },
            ...POSITIONS.map((p) => ({ value: p.value, label: p.label })),
          ]}
        />
      </div>
      <label className="flex min-h-11 items-center gap-2 text-subhead lg:justify-self-end">
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
