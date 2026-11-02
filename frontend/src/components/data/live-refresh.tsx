"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { LIVE_POLL_MS } from "@/lib/live";

export function LiveRefresh() {
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, LIVE_POLL_MS);
    return () => clearInterval(timer);
  }, [router]);
  return null;
}
