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
  plain,
}: {
  id: number;
  name: string;
  team?: Pick<TeamRef, "primary_color" | "secondary_color"> | null;
  className?: string;
  /** Load immediately (above the fold) instead of lazily. */
  eager?: boolean;
  /** Skip the built-in pool of light when the surrounding composition supplies its own. */
  plain?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const primary = team?.primary_color ?? "var(--muted-foreground)";
  return (
    <div aria-hidden className={cn("relative isolate overflow-hidden", className)}>
      {!plain && (
        <div
          className="absolute inset-0 -z-10"
          style={{
            background: `radial-gradient(60% 70% at 50% 85%, color-mix(in oklab, ${primary} 45%, transparent) 0%, transparent 70%)`,
          }}
        />
      )}
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
          className={cn(
            "absolute inset-x-0 bottom-0 mx-auto h-full object-contain object-bottom",
            plain ? "w-full" : "w-auto max-w-none",
          )}
        />
      )}
    </div>
  );
}
