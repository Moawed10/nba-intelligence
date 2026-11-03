import Link from "next/link";

import type { TeamRef } from "@/lib/api/types";

import { TeamMark } from "./team-mark";

/** A team's logo on a white disc that opens its roster page. */
export function TeamLink({
  team,
  size = "sm",
  className,
}: {
  team: Pick<TeamRef, "id" | "abbreviation" | "city" | "name" | "primary_color">;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  return (
    <Link
      href={`/teams/${team.id}`}
      aria-label={`${team.abbreviation}: ${team.city} ${team.name} roster`}
      className="relative inline-flex shrink-0 rounded-full transition-transform duration-150 after:absolute after:top-1/2 after:left-1/2 after:size-11 after:-translate-x-1/2 after:-translate-y-1/2 hover:scale-110 active:scale-95"
    >
      <TeamMark team={team} size={size} disc className={className} />
    </Link>
  );
}
