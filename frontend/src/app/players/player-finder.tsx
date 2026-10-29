"use client";

import { useRouter } from "next/navigation";

import { PlayerSearch } from "@/components/data/player-search";

export function PlayerFinder() {
  const router = useRouter();
  return (
    <section aria-labelledby="find-player">
      <h2 id="find-player" className="sr-only">
        Find a player
      </h2>
      <PlayerSearch label="Search players" onSelect={(player) => router.push(`/players/${player.id}`)} />
    </section>
  );
}
