"use client";

import Link from "next/link";

import ReflectiveCard from "@/components/bits/reflective-card";
import { PlayerCutout } from "@/components/brand/player-cutout";
import { TeamMark } from "@/components/brand/team-mark";
import type { TeamRef } from "@/lib/api/types";
import { formatStat } from "@/lib/format";

interface Props {
  player: {
    id: number;
    full_name: string;
    position: string | null;
    is_active: boolean;
    team: TeamRef | null;
  };
  season: { season: string; games_played: number; per_game: Record<string, number | null> } | null;
}

/** The selected player as a brushed-metal card that tilts toward the cursor (still under reduced motion). */
export function PlayerCard({ player, season }: Props) {
  return (
    <ReflectiveCard width="100%" height={470} radius={22} glare={0.45} blurStrength={8}>
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-2 text-[13px]">
          {player.team && <TeamMark team={player.team} size="xs" />}
          <span className="truncate font-medium">
            {player.team ? `${player.team.city} ${player.team.name}` : "Not on a current roster"}
          </span>
          <span className="ml-auto flex items-center gap-1.5 text-[color:var(--rc-muted)]">
            <span
              aria-hidden
              className={`size-1.5 rounded-full ${player.is_active ? "bg-positive" : "bg-muted-foreground"}`}
            />
            {player.is_active ? "Active" : "Former"}
          </span>
        </div>
        <PlayerCutout
          id={player.id}
          name={player.full_name}
          team={player.team}
          eager
          className="mt-3 h-44 flex-none"
        />
        <div className="mt-auto">
          <h2
            id="player-name"
            className="font-[family-name:var(--font-display)] text-[2.25rem] leading-[0.95] font-extrabold uppercase"
          >
            <Link href={`/players/${player.id}`} className="hover:underline">
              {player.full_name}
            </Link>
          </h2>
          <p className="mt-1 text-[14px] text-[color:var(--rc-muted)]">
            {[player.position, season ? `${season.season} regular season` : null].filter(Boolean).join(" · ")}
          </p>
        </div>
        {season && (
          <dl className="mt-5 grid grid-cols-4 gap-2 border-t border-white/10 pt-4">
            {(["pts", "reb", "ast"] as const).map((k) => (
              <div key={k}>
                <dt className="text-[11px] font-semibold tracking-[0.08em] text-[color:var(--rc-muted)] uppercase">
                  {k}
                </dt>
                <dd className="numeral text-[1.75rem]">{formatStat(season.per_game[k])}</dd>
              </div>
            ))}
            <div>
              <dt className="text-[11px] font-semibold tracking-[0.08em] text-[color:var(--rc-muted)] uppercase">
                GP
              </dt>
              <dd className="numeral text-[1.75rem]">{season.games_played}</dd>
            </div>
          </dl>
        )}
      </div>
    </ReflectiveCard>
  );
}
