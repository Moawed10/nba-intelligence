import { describe, expect, it } from "vitest";

import { freshnessLabel } from "@/components/data/freshness-badge";
import { isActive } from "@/components/shell/nav-config";
import {
  formatCount,
  formatGameTime,
  formatPercent,
  formatRelativeTime,
  formatSigned,
  formatStat,
} from "@/lib/format";

describe("number formatting", () => {
  it("uses one decimal and never renders missing values as zero", () => {
    expect(formatStat(27.44)).toBe("27.4");
    expect(formatStat(0)).toBe("0.0");
    expect(formatStat(null)).toBe("—");
    expect(formatStat(Number.NaN)).toBe("—");
    expect(formatCount(1234)).toBe("1,234");
    expect(formatCount(undefined)).toBe("—");
    expect(formatPercent(0.4567)).toBe("45.7%");
    expect(formatPercent(null)).toBe("—");
  });

  it("signs deltas with a true minus sign", () => {
    expect(formatSigned(2.14)).toBe("+2.1");
    expect(formatSigned(-0.96)).toBe("−1.0");
    expect(formatSigned(0.01)).toBe("±0.0");
  });
});

describe("time formatting", () => {
  const now = new Date("2026-10-28T12:00:00Z");
  it("describes recency in words", () => {
    expect(formatRelativeTime("2026-10-28T11:59:30Z", now)).toBe("just now");
    expect(formatRelativeTime("2026-10-28T11:55:00Z", now)).toBe("5 minutes ago");
    expect(formatRelativeTime("2026-10-28T09:00:00Z", now)).toBe("3 hours ago");
    expect(formatRelativeTime("2026-10-26T12:00:00Z", now)).toBe("2 days ago");
  });

  it("shows game times in Eastern time", () => {
    expect(formatGameTime("2026-10-30T23:30:00Z")).toBe("Oct 30, 7:30 PM EDT");
    expect(formatGameTime("2026-11-02T00:30:00Z")).toBe("Nov 1, 7:30 PM EST");
  });

  it("labels freshness without infrastructure jargon", () => {
    expect(freshnessLabel("fresh", "2026-10-28T11:55:00Z", now)).toBe("Updated 5 minutes ago");
    expect(freshnessLabel("stale", "2026-10-28T09:00:00Z", now)).toBe(
      "Last updated 3 hours ago · may be out of date",
    );
    expect(freshnessLabel("unavailable", null, now)).toBe("Data not yet available");
    expect(freshnessLabel("unavailable", "2026-10-28T03:00:00Z", now)).toMatch(
      /^Data temporarily unavailable · showing data through Oct 27/,
    );
  });
});

describe("navigation", () => {
  it("marks the active destination", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/players", "/")).toBe(false);
    expect(isActive("/players/201939", "/players")).toBe(true);
    expect(isActive("/playersx", "/players")).toBe(false);
  });
});
