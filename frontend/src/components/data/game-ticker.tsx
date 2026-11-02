import Link from "next/link";

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
      href={`/games?date=${game.game_date}`}
      className="flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-subhead transition-colors hover:bg-muted"
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
  if (games.length === 0) return null;
  const loop = games.length >= 4;
  return (
    <section
      aria-label={label}
      className="ticker group relative -mx-4 overflow-x-auto sm:-mx-6 lg:mx-0 lg:overflow-hidden"
    >
      <div
        className={cn("flex w-max items-center gap-1 px-4 sm:px-6 lg:px-0", loop && "ticker-track")}
        style={{ animationDuration: `${games.length * 6}s` }}
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
  );
}
