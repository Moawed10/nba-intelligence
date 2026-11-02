import type { CSSProperties, ReactNode } from "react";

import type { TeamRef } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { readableOn } from "./team-mark";

const NEUTRAL = "#16181c";

/**
 * Colors for text and fills on a team's primary color. Text is black or white by contrast; a band with
 * white text only ever darkens toward its far edge, so contrast never falls below the flat color's.
 */
export function teamBandStyle(team: Pick<TeamRef, "primary_color"> | null | undefined): CSSProperties {
  const color = team?.primary_color ?? NEUTRAL;
  const on = readableOn(color);
  const band =
    on === "#ffffff"
      ? `linear-gradient(100deg, color-mix(in oklab, ${color} 62%, #000) 0%, ${color} 100%)`
      : color;
  return { "--band": band, "--band-solid": color, "--on": on } as CSSProperties;
}

/** A full-width band in the team's color, for player and matchup features. */
export function TeamBand({
  team,
  ghost,
  className,
  children,
  labelledBy,
}: {
  team: Pick<TeamRef, "primary_color"> | null | undefined;
  /** A word set huge and faint behind the content. Decorative. */
  ghost?: string;
  className?: string;
  children: ReactNode;
  labelledBy: string;
}) {
  return (
    <section
      aria-labelledby={labelledBy}
      style={teamBandStyle(team)}
      className={cn("team-band bleed", className)}
    >
      {ghost && (
        <span
          aria-hidden
          className="display pointer-events-none absolute -right-2 bottom-[-0.06em] -z-10 text-[clamp(9rem,31cqw,30rem)] leading-[0.76] whitespace-nowrap opacity-[0.08] select-none"
        >
          {ghost}
        </span>
      )}
      {children}
    </section>
  );
}
