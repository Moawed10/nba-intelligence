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
      href={`/games/${game.id}`}
      className="flex min-h-11 shrink-0 items-center gap-2.5 rounded-md px-2.5 text-subhead transition-colors duration-150 hover:bg-muted"
    >
      {side("away")}
      <span aria-hidden className="text-footnote text-muted-foreground">@</span>
      <span className="sr-only">at</span>
      {side("home")}
      <span className={cn("kicker ml-1 tracking-[0.04em]", isLive(game) && "text-primary")}>
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

/** A slim scoreboard strip: every game in reach, scrolled by hand, never moving on its own. */
export function GameTicker({ games, label }: { games: GameSummary[]; label: string }) {
  if (games.length === 0) return null;
  return (
    <section
      aria-label={label}
      className="bleed min-w-0 border-y border-border"
    >
      <div className="scroll-quiet relative overflow-x-auto"
      >
        <ul className="flex w-max items-center">
          {games.map((g) => (
            <li key={g.id} className="flex items-center">
              <Item game={g} />
              <span aria-hidden className="mx-1 h-5 w-px bg-border" />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
