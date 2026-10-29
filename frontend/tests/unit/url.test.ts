import { describe, expect, it } from "vitest";

import { formatGameDate, formatGameValue, formatHeight } from "@/lib/format";
import { hrefWith, oneOf, param, positiveInt } from "@/lib/url";

describe("URL state helpers", () => {
  it("reads the first value of a search param", () => {
    expect(param({ a: ["x", "y"], b: "z" }, "a")).toBe("x");
    expect(param({ b: "z" }, "b")).toBe("z");
    expect(param({}, "c")).toBeUndefined();
  });

  it("accepts only positive integers for pages", () => {
    expect(positiveInt("3")).toBe(3);
    expect(positiveInt("0")).toBe(1);
    expect(positiveInt("-2")).toBe(1);
    expect(positiveInt("1.5")).toBe(1);
    expect(positiveInt("abc")).toBe(1);
    expect(positiveInt(undefined)).toBe(1);
  });

  it("restricts values to an allow-list", () => {
    expect(oneOf("reb", ["pts", "reb"] as const, "pts")).toBe("reb");
    expect(oneOf("drop table", ["pts", "reb"] as const, "pts")).toBe("pts");
  });

  it("builds canonical URLs without empty values", () => {
    expect(hrefWith("/players", { team: "1", position: undefined }, { page: 2 })).toBe("/players?team=1&page=2");
    expect(hrefWith("/players", { team: "1" }, { team: undefined, page: null })).toBe("/players");
    expect(hrefWith("/p", {}, { q: "a b&c" })).toBe("/p?q=a+b%26c");
  });
});

describe("profile formatters", () => {
  it("formats heights in feet and inches", () => {
    expect(formatHeight(83)).toBe("6′11″");
    expect(formatHeight(72)).toBe("6′0″");
    expect(formatHeight(null)).toBe("—");
  });

  it("formats calendar dates without shifting them across time zones", () => {
    expect(formatGameDate("2026-01-01")).toBe("Jan 1");
    expect(formatGameDate("2025-12-31", true)).toBe("Dec 31, 2025");
  });

  it("shows single-game counts as whole numbers and minutes with a decimal", () => {
    expect(formatGameValue(21)).toBe("21");
    expect(formatGameValue(34.5)).toBe("34.5");
    expect(formatGameValue(null)).toBe("—");
  });
});
