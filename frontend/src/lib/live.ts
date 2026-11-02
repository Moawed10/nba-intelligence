import type { GameSummary } from "@/lib/api/types";

export const LIVE_POLL_MS = 30_000;
const LONGEST_GAME_MS = 6 * 60 * 60_000;

export function isLive(game: GameSummary): boolean {
  if (game.status !== "in_progress") return false;
  return !game.tipoff_at || Date.now() - Date.parse(game.tipoff_at) < LONGEST_GAME_MS;
}

export function liveLabel(game: GameSummary): string {
  if (!isLive(game)) return "Waiting for the final score";
  return game.live_status ? `Live · ${game.live_status}` : "Live";
}
