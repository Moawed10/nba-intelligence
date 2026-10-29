"use client";

import { useState } from "react";

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

/**
 * The player's photo (served and cached by our API, never fetched from nba.com by the browser) on a
 * team-tinted disc, or their initials when there is no id or no photo. Decorative: the name is in text.
 */
export function PlayerAvatar({
  id,
  name,
  team,
  size = "md",
  className,
}: {
  id?: number;
  name: string;
  team?: Pick<TeamRef, "primary_color"> | null;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const color = team?.primary_color ?? "var(--muted-foreground)";
  const photo = id != null && !failed;
  return (
    <span
      aria-hidden
      style={{
        background: `color-mix(in oklab, ${color} 28%, var(--card))`,
        boxShadow: `inset 0 0 0 1.5px color-mix(in oklab, ${color} 70%, transparent)`,
      }}
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold tracking-tight text-foreground",
        SIZE[size],
        className,
      )}
    >
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element -- same-origin cached PNGs; next/image adds nothing
        <img
          src={`/api/v1/players/${id}/photo`}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="absolute inset-x-0 bottom-0 h-[115%] w-full object-cover object-top"
        />
      ) : (
        initials(name)
      )}
    </span>
  );
}
