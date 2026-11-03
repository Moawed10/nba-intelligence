export const TREND_STATS = [
  { value: "pts", label: "Points", short: "PTS" },
  { value: "reb", label: "Rebounds", short: "REB" },
  { value: "ast", label: "Assists", short: "AST" },
  { value: "fg3m", label: "3-pointers made", short: "3PM" },
  { value: "stl", label: "Steals", short: "STL" },
  { value: "blk", label: "Blocks", short: "BLK" },
  { value: "min", label: "Minutes", short: "MIN" },
] as const;

export type TrendStat = (typeof TREND_STATS)[number]["value"];

export const TREND_STAT_VALUES = TREND_STATS.map((s) => s.value);

export const TREND_VIEWS = [
  { value: "season", label: "This season" },
  { value: "years", label: "By year" },
  { value: "all", label: "All time" },
] as const;

export type TrendView = (typeof TREND_VIEWS)[number]["value"];

export const TREND_VIEW_VALUES = TREND_VIEWS.map((v) => v.value);
