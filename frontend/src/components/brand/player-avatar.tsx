import type { TeamRef } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const SIZE = {
  sm: "size-8 text-[0.6875rem]",
  md: "size-10 text-xs",
  lg: "size-16 text-lg",
  xl: "size-24 text-2xl",
} as const;

export function initials(name: string): string {
  const parts = name
    .replace(/\b(Jr\.?|Sr\.?|II|III|IV)\b/g, "")
    .trim()
    .split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** Initials in a team-tinted disc. Real headshots are NBA property, so none are shown. */
export function PlayerAvatar({
  name,
  team,
  size = "md",
  className,
}: {
  name: string;
  team?: Pick<TeamRef, "primary_color"> | null;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  const color = team?.primary_color ?? "var(--muted-foreground)";
  return (
    <span
      aria-hidden
      style={{
        background: `color-mix(in oklab, ${color} 28%, var(--card))`,
        boxShadow: `inset 0 0 0 1.5px color-mix(in oklab, ${color} 70%, transparent)`,
      }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold tracking-tight text-foreground",
        SIZE[size],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
