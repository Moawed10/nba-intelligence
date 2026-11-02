"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import type { GameSummary } from "@/lib/api/types";
import { LIVE_POLL_MS, shouldFollow } from "@/lib/live";

export function LiveRefresh({ games }: { games: GameSummary[] }) {
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible" && games.some(shouldFollow)) router.refresh();
    }, LIVE_POLL_MS);
    return () => clearInterval(timer);
  }, [router, games]);
  return null;
}
