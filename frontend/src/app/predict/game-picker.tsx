"use client";

import { useRouter } from "next/navigation";
import { type CSSProperties, useTransition } from "react";

import AnimatedList from "@/components/bits/animated-list";
import { TeamMark } from "@/components/brand/team-mark";
import type { GameSummary } from "@/lib/api/types";
import { formatGameDate, formatGameTime } from "@/lib/format";
import { hrefWith } from "@/lib/url";
import { cn } from "@/lib/utils";

/** The list adopts the app's tokens so it reads correctly in both themes. */
const TOKENS = {
  "--al-tile": "var(--card)",
  "--al-tile-edge": "var(--border)",
  "--al-tile-highlight": "transparent",
  "--al-tile-shadow": "none",
  "--al-well": "transparent",
  "--al-ink": "var(--foreground)",
  "--al-muted": "var(--muted-foreground)",
  "--al-thumb": "var(--border)",
  "--al-hover": "none",
  "--al-active": "none",
} as CSSProperties;

export interface PickerForecast {
  values: { point: number; lower: number; upper: number }[];
  notes: string[];
}

/** Upcoming games as a keyboard-navigable list (arrow keys, Home, End, Enter); choosing one loads its forecast. */
export function GamePicker({
  games,
  playerId,
  teamId,
  selectedId,
  forecasts,
}: {
  games: GameSummary[];
  playerId: number;
  teamId: number;
  selectedId: string | null;
  /** Per game id: points, rebounds and assists with their likely ranges, and what sets the game
   * apart; null when the game can't be forecast. */
  forecasts: Record<string, PickerForecast | null>;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const selected = Math.max(
    0,
    games.findIndex((g) => g.id === selectedId),
  );

  const anyForecast = Object.values(forecasts).some(Boolean);
  return (
    <div aria-busy={pending} className={cn("space-y-3 transition-opacity", pending && "opacity-70")}>
      {anyForecast && (
        <p className="flex items-center justify-between gap-3 text-footnote text-muted-foreground">
          <span>Predicted stat line for each game, with its likely range</span>
          <span aria-hidden className="kicker shrink-0 text-primary">
            Predicted
          </span>
        </p>
      )}
      <AnimatedList
        label="Upcoming games"
        items={games.map((g) => ({ id: g.id, title: g.id }))}
        initialSelectedIndex={selected}
        selectOnHover={false}
        frame={false}
        animation="none"
        width="100%"
        maxHeight={420}
        gap={6}
        radius={12}
        accentColor="var(--primary)"
        style={TOKENS}
        onItemSelect={(_, index) =>
          startTransition(() =>
            router.push(hrefWith("/predict", {}, { player: playerId, game: games[index].id }), {
              scroll: false,
            }),
          )
        }
        renderItem={(_, index, isSelected) => {
          const game = games[index];
          const home = game.home.team.id === teamId;
          const opponent = home ? game.away.team : game.home.team;
          const forecast = forecasts[game.id];
          return (
            <span className="flex w-full items-center gap-3">
              <TeamMark team={opponent} size="sm" />
              <span className="min-w-0 flex-1">
                <span className={cn("block font-medium", isSelected && "text-primary")}>
                  {home ? "vs" : "@"} {opponent.city} {opponent.name}
                </span>
                <span className="block text-footnote text-muted-foreground">
                  {game.tipoff_at ? formatGameTime(game.tipoff_at) : formatGameDate(game.game_date, true)}
                </span>
                {forecast && forecast.notes.length > 0 && (
                  <span className="mt-0.5 block text-footnote text-primary">{forecast.notes.join(" · ")}</span>
                )}
              </span>
              {forecast ? (
                <span className="flex shrink-0 gap-3 text-right">
                  <span className="sr-only">Predicted:</span>
                  {forecast.values.map((v, i) => (
                    <span key={i} className="min-w-9">
                      <span className="numeral block text-title3">{Math.round(v.point)}</span>
                      <span className="kicker block">{["PTS", "REB", "AST"][i]}</span>
                      <span className="block text-kicker text-muted-foreground tabular-nums">
                        <span className="sr-only">likely </span>
                        {Math.round(v.lower)}–{Math.round(v.upper)}
                      </span>
                    </span>
                  ))}
                </span>
              ) : (
                game.id === selectedId && <span className="kicker text-primary">Selected</span>
              )}
            </span>
          );
        }}
      />
    </div>
  );
}
