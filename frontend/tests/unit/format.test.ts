import { describe, expect, it } from "vitest";

import { freshnessLabel } from "@/components/data/freshness-badge";
import { isActive } from "@/components/shell/nav-config";
import {
  formatCount,
  formatGameTime,
  playerTeamLabel,
  formatPercent,
  formatShooting,
  formatRelativeTime,
  formatSigned,
  formatStat,
} from "@/lib/format";
import { milestoneLabel, roughReturn } from "@/lib/format";

describe("number formatting", () => {
  it("uses one decimal and never renders missing values as zero", () => {
    expect(formatStat(27.44)).toBe("27.4");
    expect(formatStat(0)).toBe("0.0");
    expect(formatStat(null)).toBe("—");
    expect(formatStat(Number.NaN)).toBe("—");
    expect(formatCount(1234)).toBe("1,234");
    expect(formatCount(undefined)).toBe("—");
    expect(formatPercent(0.4567)).toBe("45.7%");
    expect(formatShooting(0.5)).toBe("50.0%");
    expect(formatShooting(null)).toBe("—");
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

  it("says where a player is now, or when and where they finished", () => {
    expect(playerTeamLabel({ is_active: true, team: { abbreviation: "LAL" } })).toBe("LAL");
    expect(playerTeamLabel({ is_active: true, team: null })).toBe("No current team");
    expect(playerTeamLabel({ is_active: false, to_year: 1997, final_team: "HOU" })).toBe(
      "Retired 1998 · HOU",
    );
    expect(playerTeamLabel({ is_active: false, to_year: 1997, final_team: null })).toBe("Retired 1998");
    expect(playerTeamLabel({ is_active: false, to_year: null })).toBe("Former player");
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

describe("milestoneLabel", () => {
  const box = (pts: number, reb: number, ast: number, stl = 0, blk = 0) => ({ pts, reb, ast, stl, blk });

  it("names the line by how many counting stats reached 10", () => {
    expect(milestoneLabel(box(31, 18, 10))).toBe("Triple-double");
    expect(milestoneLabel(box(45, 15, 6))).toBe("Double-double");
    expect(milestoneLabel(box(20, 10, 10, 10))).toBe("Quadruple-double");
    expect(milestoneLabel(box(44, 8, 6))).toBeNull();
  });
});

describe("roughReturn", () => {
  const now = new Date("2099-11-03T18:00:00Z");

  it("states a date and a rough span", () => {
    expect(roughReturn("2099-11-06", now)).toBe("Estimated back Nov 6 (about 3 days)");
    expect(roughReturn("2099-11-04", now)).toBe("Estimated back Nov 4 (about 1 day)");
    expect(roughReturn("2099-12-15", now)).toBe("Estimated back Dec 15 (about 6 weeks)");
  });

  it("never invents a date", () => {
    expect(roughReturn(null, now)).toBeNull();
    expect(roughReturn("2099-11-01", now)).toBe("Return date not updated");
  });
});
