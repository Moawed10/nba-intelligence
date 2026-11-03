import Link from "next/link";

import { PlayerCutout } from "@/components/brand/player-cutout";
import { TeamBand } from "@/components/brand/team-band";
import { TeamLink } from "@/components/brand/team-link";
import type { TeamRef } from "@/lib/api/types";
import { formatStat } from "@/lib/format";
import { targetLabel } from "@/lib/models";

interface Props {
  player: {
    id: number;
    full_name: string;
    jersey_number?: string | null;
    position: string | null;
    is_active: boolean;
    team: TeamRef | null;
  };
  season: { season: string; games_played: number; per_game: Record<string, number | null> } | null;
}

/** The selected player as a team-colored band: who the forecast is for, with their season so far. */
export function PlayerCard({ player, season, className }: Props & { className?: string }) {
  return (
    <TeamBand team={player.team} labelledBy="player-name" className={className}>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="flex min-w-0 items-end gap-4 sm:gap-6">
          <PlayerCutout
            id={player.id}
            name={player.full_name}
            team={player.team}
            eager
            plain
            className="mt-4 h-28 w-36 shrink-0 sm:h-40 sm:w-52"
          />
          <div className="min-w-0 pb-4">
            <p className="kicker flex items-center gap-2">
              {player.team && <TeamLink team={player.team} size="xs" />}
              {player.team ? `${player.team.city} ${player.team.name}` : "Not on a current roster"}
              {player.jersey_number && ` · #${player.jersey_number}`}
              {" · "}
              {player.is_active ? "Active" : "Former"}
            </p>
            <h2 id="player-name" className="display mt-2 text-[clamp(2.5rem,6vw,4.5rem)]">
              <Link href={`/players/${player.id}`} className="underline-offset-4 hover:underline">
                {player.full_name}
              </Link>
            </h2>
            <p className="mt-1 text-footnote font-medium">
              {[player.position, season ? `${season.season} regular season` : null].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
        {season && (
          <dl className="flex gap-6 pb-4 sm:gap-8">
            {(["pts", "reb", "ast"] as const).map((k) => (
              <div key={k}>
                <dd className="numeral text-[2.5rem] sm:text-[3.25rem]">{formatStat(season.per_game[k])}</dd>
                <dt className="kicker mt-1">
                  <span aria-hidden>{k}</span>
                  <span className="sr-only">{targetLabel(k)} per game</span>
                </dt>
              </div>
            ))}
            <div>
              <dd className="numeral text-[2.5rem] sm:text-[3.25rem]">{season.games_played}</dd>
              <dt className="kicker mt-1">GP</dt>
            </div>
          </dl>
        )}
      </div>
    </TeamBand>
  );
}
