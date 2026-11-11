import { oneOf, param, positiveInt, SEASON_LABEL, type SearchParams } from "@/lib/url";

export const POSITIONS = [
  { value: "G", label: "Guards" },
  { value: "F", label: "Forwards" },
  { value: "C", label: "Centers" },
] as const;

export const SORT_COLUMNS = [
  { key: "games", label: "GP", description: "Games played" },
  { key: "min", label: "MIN", description: "Minutes per game" },
  { key: "pts", label: "PTS", description: "Points per game" },
  { key: "reb", label: "REB", description: "Rebounds per game" },
  { key: "ast", label: "AST", description: "Assists per game" },
  { key: "fg3m", label: "3PM", description: "3-pointers made per game" },
  { key: "stl", label: "STL", description: "Steals per game" },
  { key: "blk", label: "BLK", description: "Blocks per game" },
  { key: "tov", label: "TOV", description: "Turnovers per game" },
] as const;

/** Ranked only among players with enough made shots (the NBA's qualifying minimums). */
export const SHOOTING_COLUMNS = [
  { key: "fg_pct", label: "FG%", description: "Share of all shots made" },
  { key: "fg3_pct", label: "3P%", description: "Share of 3-pointers made" },
  { key: "ft_pct", label: "FT%", description: "Share of free throws made" },
  {
    key: "ts_pct",
    label: "TS%",
    description: "True shooting: scoring efficiency counting 3-pointers and free throws",
  },
] as const;

export type ShootingKey = (typeof SHOOTING_COLUMNS)[number]["key"];
export type SortKey = (typeof SORT_COLUMNS)[number]["key"] | ShootingKey | "full_name";
const SORTS = [
  "full_name",
  ...SORT_COLUMNS.map((c) => c.key),
  ...SHOOTING_COLUMNS.map((c) => c.key),
] as const;

export function isShooting(key: string): key is ShootingKey {
  return SHOOTING_COLUMNS.some((c) => c.key === key);
}

export interface DirectoryFilters {
  season?: string;
  team?: string;
  position?: string;
  status?: string;
  sort?: string;
}

export interface DirectoryState extends DirectoryFilters {
  page: number;
  sortKey: SortKey;
  descending: boolean;
}

export const DEFAULT_SORT = "-pts";
export const ALL_TIME = "all";

/** All time lists former players by default (the greats are mostly retired); a season does not. */
export function includesFormer(filters: Pick<DirectoryFilters, "season" | "status">): boolean {
  return filters.status === "all" || (filters.season === ALL_TIME && filters.status !== "active");
}

export function parseDirectory(params: SearchParams): DirectoryState {
  const team = param(params, "team");
  const season = param(params, "season");
  const rawSort = param(params, "sort") ?? DEFAULT_SORT;
  const descending = rawSort.startsWith("-");
  const sortKey = oneOf(rawSort.replace(/^-/, ""), SORTS, "pts");
  const sort = `${descending ? "-" : ""}${sortKey}`;
  return {
    season: season && (season === ALL_TIME || SEASON_LABEL.test(season)) ? season : undefined,
    team: team && /^\d+$/.test(team) ? team : undefined,
    position: oneOf(param(params, "position"), ["G", "F", "C", ""] as const, "") || undefined,
    status: oneOf(param(params, "status"), ["all", "active", ""] as const, "") || undefined,
    sort: sort === DEFAULT_SORT ? undefined : sort,
    page: positiveInt(param(params, "page")),
    sortKey,
    descending,
  };
}
