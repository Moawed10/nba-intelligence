"use client";

import { useState } from "react";

import { PlayerSearch, playerDetails } from "@/components/data/player-search";
import type { PlayerSearchResult } from "@/lib/api/types";

export function PlayerFinder() {
  const [selected, setSelected] = useState<PlayerSearchResult | null>(null);
  return (
    <section aria-labelledby="find-player" className="space-y-4">
      <h2 id="find-player" className="sr-only">
        Find a player
      </h2>
      <PlayerSearch label="Search players" onSelect={setSelected} />
      {selected && (
        <div role="status" className="max-w-xl rounded-xl bg-card px-4 py-3">
          <p className="text-headline font-semibold">{selected.full_name}</p>
          <p className="text-subhead text-muted-foreground">
            {playerDetails(selected) || "No current team"}
          </p>
        </div>
      )}
    </section>
  );
}
