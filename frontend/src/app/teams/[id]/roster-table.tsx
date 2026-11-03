"use client";

import Link from "next/link";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { type Column, DataTable } from "@/components/data/data-table";
import type { DirectoryPlayer, PlayerSummary } from "@/lib/api/types";
import { formatPercent, formatStat } from "@/lib/format";

export type RosterRow = PlayerSummary & { season_averages?: DirectoryPlayer["season_averages"] };

const stat = (key: "min" | "pts" | "reb" | "ast" | "fg3m" | "stl" | "blk", header: string, description: string): Column<RosterRow> => ({
  key,
  header,
  description,
  numeric: true,
  cell: (p) => formatStat(p.season_averages?.[key]),
  sortValue: (p) => p.season_averages?.[key] ?? null,
});

const COLUMNS: Column<RosterRow>[] = [
  {
    key: "player",
    header: "Player",
    sortValue: (p) => p.full_name,
    cell: (p) => (
      <span className="flex items-center gap-2 sm:gap-3">
        <PlayerAvatar id={p.id} name={p.full_name} team={p.team} size="sm" className="sm:size-10" />
        <Link
          href={`/players/${p.id}`}
          className="w-24 font-medium whitespace-normal transition-colors duration-150 hover:text-primary sm:w-auto"
        >
          {p.full_name}
        </Link>
      </span>
    ),
  },
  stat("pts", "PTS", "Points per game"),
  stat("reb", "REB", "Rebounds per game"),
  stat("ast", "AST", "Assists per game"),
  stat("min", "MIN", "Minutes per game"),
  stat("fg3m", "3PM", "3-pointers made per game"),
  stat("stl", "STL", "Steals per game"),
  stat("blk", "BLK", "Blocks per game"),
  {
    key: "fg",
    header: "FG%",
    description: "Field goal percentage",
    numeric: true,
    cell: (p) => formatPercent(p.season_averages?.fg_pct),
    sortValue: (p) => p.season_averages?.fg_pct ?? null,
  },
  {
    key: "gp",
    header: "GP",
    description: "Games played",
    numeric: true,
    cell: (p) => p.season_averages?.games_played ?? "—",
    sortValue: (p) => p.season_averages?.games_played ?? null,
  },
  { key: "pos", header: "Pos", description: "Position", cell: (p) => p.position ?? "—", sortValue: (p) => p.position ?? null },
];

export function RosterTable({ players, caption }: { players: RosterRow[]; caption: string }) {
  return (
    <DataTable
      caption={caption}
      columns={COLUMNS}
      rows={players}
      rowKey={(p) => String(p.id)}
      initialSort={{ key: "pts", direction: "descending" }}
    />
  );
}
