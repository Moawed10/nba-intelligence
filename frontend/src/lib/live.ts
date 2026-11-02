import type { GameSummary } from "@/lib/api/types";

export const LIVE_POLL_MS = 5_000;
export const IDLE_POLL_MS = 60_000;
const LONGEST_GAME_MS = 6 * 60 * 60_000;
const BEFORE_TIPOFF_MS = 15 * 60_000;

export function isLive(game: GameSummary): boolean {
  if (game.status !== "in_progress") return false;
  return !game.tipoff_at || Date.now() - Date.parse(game.tipoff_at) < LONGEST_GAME_MS;
}

export function shouldFollow(game: GameSummary): boolean {
  if (isLive(game)) return true;
  if (game.status !== "scheduled" || !game.tipoff_at) return false;
  const untilTipoff = Date.parse(game.tipoff_at) - Date.now();
  return untilTipoff < BEFORE_TIPOFF_MS && untilTipoff > -LONGEST_GAME_MS;
}

export function liveLabel(game: GameSummary): string {
  if (!isLive(game)) return "Waiting for the final score";
  return game.live_status ? `Live · ${game.live_status}` : "Live";
}
