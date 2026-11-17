"use client";

import { useEffect, useRef, useState } from "react";

import type { GameSummary } from "@/lib/api/types";
import { formatLiveClock, liveLabel, parseLiveClock, runningClock, type LiveClock } from "@/lib/live";

type Stamp = { clock: LiveClock; at: number };

export function LiveLabel({ game }: { game: GameSummary }) {
  const stamps = useRef<{ latest: Stamp | null; previous: Stamp | null }>({ latest: null, previous: null });
  const [shown, setShown] = useState<{ from: string; text: string } | null>(null);
  const status = game.live_status;

  useEffect(() => {
    const clock = parseLiveClock(status);
    if (!status || !clock) {
      stamps.current = { latest: null, previous: null };
      return;
    }
    const seen = stamps.current.latest;
    if (!seen || formatLiveClock(seen.clock) !== formatLiveClock(clock)) {
      stamps.current = { latest: { clock, at: Date.now() }, previous: seen };
    }
    const timer = setInterval(() => {
      const { latest, previous } = stamps.current;
      if (!latest) return;
      const text = formatLiveClock(
        runningClock(latest.clock, previous?.clock ?? null, Date.now() - latest.at),
      );
      setShown({ from: status, text });
    }, 1_000);
    return () => clearInterval(timer);
  }, [status]);

  return <>{liveLabel({ ...game, live_status: shown?.from === status ? shown.text : status })}</>;
}
