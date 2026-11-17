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

const CLOCK = /^(.*\S)\s+(\d{1,2}):(\d{2})$/;
export const CLOCK_COAST_MS = 20_000;

export type LiveClock = { period: string; seconds: number };

export function parseLiveClock(status: string | null | undefined): LiveClock | null {
  const match = status ? CLOCK.exec(status.trim()) : null;
  if (!match) return null;
  return { period: match[1], seconds: Number(match[2]) * 60 + Number(match[3]) };
}

export function formatLiveClock({ period, seconds }: LiveClock): string {
  return `${period} ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * The feed stamps the clock at each play, so between plays the shown clock runs on from the last
 * stamp — but only once the clock has been seen moving, and for at most CLOCK_COAST_MS, so a
 * timeout or free throws freeze it instead of running it down.
 */
export function runningClock(
  latest: LiveClock,
  previous: LiveClock | null,
  sinceLatestMs: number,
): LiveClock {
  const moving = previous !== null && previous.period === latest.period && previous.seconds > latest.seconds;
  if (!moving) return latest;
  const elapsed = Math.floor(Math.min(Math.max(sinceLatestMs, 0), CLOCK_COAST_MS) / 1000);
  return { period: latest.period, seconds: Math.max(latest.seconds - elapsed, 0) };
}
