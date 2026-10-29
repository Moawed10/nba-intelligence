import type { CSSProperties } from "react";

import type { TeamRef } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const SIZE = {
  xs: "size-6 rounded-md text-[0.5625rem]",
  sm: "size-8 rounded-lg text-[0.625rem]",
  md: "size-10 rounded-lg text-xs",
  lg: "size-14 rounded-xl text-sm",
  xl: "size-20 rounded-2xl text-lg",
} as const;

/** Black or white, whichever reads better on a team color (WCAG relative luminance). */
export function readableOn(hex: string): string {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 0.18 ? "#0b0b0d" : "#ffffff";
}

export function teamStyle(team: Pick<TeamRef, "primary_color"> | null | undefined): CSSProperties {
  const color = team?.primary_color;
  return color ? { background: color, color: readableOn(color) } : {};
}

/** A team monogram in its primary color. Decorative: the abbreviation is always also in text. */
export function TeamMark({
  team,
  size = "sm",
  className,
}: {
  team: Pick<TeamRef, "abbreviation" | "primary_color"> | null | undefined;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      style={teamStyle(team)}
      className={cn(
        "inline-flex shrink-0 items-center justify-center bg-muted font-semibold tracking-wide text-muted-foreground ring-1 ring-white/10 ring-inset",
        SIZE[size],
        className,
      )}
    >
      {team?.abbreviation ?? "—"}
    </span>
  );
}
