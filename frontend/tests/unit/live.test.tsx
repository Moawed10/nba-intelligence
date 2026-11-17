import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveLabel } from "@/components/data/live-label";
import type { GameSummary } from "@/lib/api/types";
import { CLOCK_COAST_MS, formatLiveClock, parseLiveClock, runningClock } from "@/lib/live";

describe("live clock", () => {
  it("reads the period and the time left from the live status", () => {
    expect(parseLiveClock("Q2 6:25")).toEqual({ period: "Q2", seconds: 385 });
    expect(parseLiveClock("OT1 0:04")).toEqual({ period: "OT1", seconds: 4 });
    expect(parseLiveClock("Half")).toBeNull();
    expect(parseLiveClock(null)).toBeNull();
    expect(formatLiveClock({ period: "Q4", seconds: 65 })).toBe("Q4 1:05");
  });

  it("runs down only after the clock has been seen moving", () => {
    const latest = { period: "Q2", seconds: 385 };
    expect(runningClock(latest, null, 5_000)).toEqual(latest);
    expect(runningClock(latest, { period: "Q2", seconds: 385 }, 5_000)).toEqual(latest);
    expect(runningClock(latest, { period: "Q1", seconds: 3 }, 5_000)).toEqual(latest);
    expect(runningClock(latest, { period: "Q2", seconds: 400 }, 5_400).seconds).toBe(380);
  });

  it("stops after a short coast and never goes below zero", () => {
    const previous = { period: "Q3", seconds: 50 };
    expect(runningClock({ period: "Q3", seconds: 40 }, previous, 600_000).seconds).toBe(
      40 - CLOCK_COAST_MS / 1000,
    );
    expect(runningClock({ period: "Q3", seconds: 3 }, { period: "Q3", seconds: 9 }, 15_000).seconds).toBe(0);
  });
});

const game = (live_status: string | null) => ({ status: "in_progress", live_status }) as GameSummary;

describe("LiveLabel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("ticks between updates once the clock moves, and snaps to each new update", () => {
    const { rerender } = render(<LiveLabel game={game("Q2 6:40")} />);
    expect(screen.getByText("Live · Q2 6:40")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(3_000));
    expect(screen.getByText("Live · Q2 6:40")).toBeInTheDocument();

    rerender(<LiveLabel game={game("Q2 6:25")} />);
    expect(screen.getByText("Live · Q2 6:25")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(4_000));
    expect(screen.getByText("Live · Q2 6:21")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(60_000));
    expect(
      screen.getByText(`Live · ${formatLiveClock({ period: "Q2", seconds: 385 - CLOCK_COAST_MS / 1000 })}`),
    ).toBeInTheDocument();

    rerender(<LiveLabel game={game("Q2 6:10")} />);
    expect(screen.getByText("Live · Q2 6:10")).toBeInTheDocument();
  });

  it("shows a break in play as the source gives it", () => {
    render(<LiveLabel game={game("Half")} />);
    act(() => vi.advanceTimersByTime(5_000));
    expect(screen.getByText("Live · Half")).toBeInTheDocument();
  });
});
