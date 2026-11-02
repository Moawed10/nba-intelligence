"use client";

import { Pause, Play } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { TeamMark } from "@/components/brand/team-mark";
import type { GameSummary } from "@/lib/api/types";
import { formatGameDate, formatGameTime } from "@/lib/format";
import { isLive, liveLabel } from "@/lib/live";
import { cn } from "@/lib/utils";

function Item({ game }: { game: GameSummary }) {
  const final = game.status === "final";
  const live = game.status === "in_progress" && game.home.score != null;
  const homeWon = final && (game.home.score ?? 0) > (game.away.score ?? 0);
  const side = (which: "away" | "home") => {
    const entry = game[which];
    const won = final && (which === "home") === homeWon;
    return (
      <span className="flex items-center gap-1.5">
        <TeamMark team={entry.team} size="xs" />
        <span className={cn("font-semibold", final && !won && "text-muted-foreground")}>
          {entry.team.abbreviation}
        </span>
        {(final || live) && (
          <span className={cn("numeral text-headline", final && !won && "text-muted-foreground")}>
            {entry.score}
          </span>
        )}
      </span>
    );
  };
  return (
    <Link
      href={`/games/${game.id}`}
      className="flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-subhead pointer-coarse:min-h-11 transition-colors hover:bg-muted"
    >
      {side("away")}
      <span className="text-muted-foreground">@</span>
      {side("home")}
      <span className={cn("kicker", isLive(game) && "text-primary")}>
        {final
          ? "Final"
          : game.status === "in_progress"
            ? liveLabel(game)
            : game.tipoff_at
              ? formatGameTime(game.tipoff_at)
              : formatGameDate(game.game_date)}
      </span>
    </Link>
  );
}

/**
 * A broadcast-style scoreboard strip. It scrolls slowly, pauses on hover or keyboard focus, and
 * stays still (scrollable by hand) when reduced motion is requested.
 */
export function GameTicker({ games, label }: { games: GameSummary[]; label: string }) {
  const [paused, setPaused] = useState(false);
  if (games.length === 0) return null;
  const loop = games.length >= 4;
  return (
    <div className="flex items-center gap-2">
      <section
        aria-label={label}
        className="ticker group relative -mx-4 min-w-0 flex-1 overflow-x-auto sm:-mx-6 lg:mx-0 lg:overflow-hidden"
      >
        <div
          className={cn("flex w-max items-center gap-1 px-4 sm:px-6 lg:px-0", loop && "ticker-track")}
          style={{
            animationDuration: `${games.length * 6}s`,
            animationPlayState: paused ? "paused" : undefined,
          }}
        >
          <ul className="flex items-center gap-1">
            {games.map((g) => (
              <li key={g.id} className="flex items-center gap-1">
                <Item game={g} />
                <span aria-hidden className="h-5 w-px bg-border" />
              </li>
            ))}
          </ul>
          {loop && (
            <ul aria-hidden className="flex items-center gap-1" inert>
              {games.map((g) => (
                <li key={g.id} className="flex items-center gap-1">
                  <Item game={g} />
                  <span className="h-5 w-px bg-border" />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      {loop && (
        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          aria-label={paused ? "Play scores" : "Pause scores"}
          className="hidden size-9 shrink-0 items-center justify-center rounded-full border border-border transition-colors hover:border-foreground/25 motion-reduce:hidden lg:inline-flex"
        >
          {paused ? <Play aria-hidden className="size-4" /> : <Pause aria-hidden className="size-4" />}
        </button>
      )}
    </div>
  );
}
