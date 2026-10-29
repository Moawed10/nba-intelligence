"use client";

import { useState } from "react";

import type { TeamRef } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { initials } from "./player-avatar";

/**
 * The player's transparent photo standing in a pool of team-colored light, broadcast style.
 * Falls back to oversized initials when the source has no photo. Decorative: the name is in text.
 */
export function PlayerCutout({
  id,
  name,
  team,
  className,
  eager,
}: {
  id: number;
  name: string;
  team?: Pick<TeamRef, "primary_color" | "secondary_color"> | null;
  className?: string;
  /** Load immediately (above the fold) instead of lazily. */
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const primary = team?.primary_color ?? "var(--muted-foreground)";
  const secondary = team?.secondary_color ?? primary;
  return (
    <div aria-hidden className={cn("relative isolate overflow-hidden", className)}>
      <div
        className="absolute inset-0 -z-10"
        style={{
          background: `radial-gradient(60% 70% at 50% 85%, color-mix(in oklab, ${primary} 70%, transparent) 0%, transparent 70%), radial-gradient(40% 40% at 78% 20%, color-mix(in oklab, ${secondary} 35%, transparent) 0%, transparent 70%)`,
        }}
      />
      <div
        className="absolute inset-x-[8%] bottom-0 -z-10 h-[8%] rounded-[50%] blur-xl"
        style={{ background: `color-mix(in oklab, ${primary} 60%, black)` }}
      />
      {failed ? (
        <span className="numeral absolute inset-0 flex items-center justify-center text-[clamp(4rem,14vw,9rem)] text-foreground/80">
          {initials(name)}
        </span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- same-origin cached PNG; next/image adds nothing
        <img
          src={`/api/v1/players/${id}/photo?size=large`}
          alt=""
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          onError={() => setFailed(true)}
          className="absolute inset-x-0 bottom-0 mx-auto h-full w-auto max-w-none object-contain object-bottom drop-shadow-[0_20px_30px_rgba(0,0,0,0.45)]"
        />
      )}
    </div>
  );
}
