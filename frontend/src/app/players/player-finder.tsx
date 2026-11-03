"use client";

import { useRouter } from "next/navigation";

import { PlayerSearch } from "@/components/data/player-search";
import { cn } from "@/lib/utils";

export function PlayerFinder({ compact }: { compact?: boolean }) {
  const router = useRouter();
  return (
    <section aria-labelledby="find-player" className={cn(compact && "w-full sm:w-80")}>
      <h2 id="find-player" className="sr-only">
        Find a player
      </h2>
      <PlayerSearch
        label="Search players"
        hideLabel={compact}
        className={compact ? undefined : "max-w-xl"}
        onSelect={(player) => router.push(`/players/${player.id}`)}
      />
    </section>
  );
}
