import type { Transition } from "motion/react";

/** One motion scale for interactive (JS) animation, in seconds; entrance motion lives in globals.css. */
export const DURATION = { micro: 0.15, hover: 0.2, panel: 0.28, page: 0.24, data: 0.3 } as const;

export const EASE_OUT: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const SPRING: Record<"snappy" | "gentle", Transition> = {
  snappy: { type: "spring", stiffness: 420, damping: 38 },
  gentle: { type: "spring", stiffness: 260, damping: 30 },
};
