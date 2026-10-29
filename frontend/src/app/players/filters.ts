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
] as const;

export type SortKey = (typeof SORT_COLUMNS)[number]["key"] | "full_name";
const SORTS = ["full_name", ...SORT_COLUMNS.map((c) => c.key)] as const;

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

export function parseDirectory(params: SearchParams): DirectoryState {
  const team = param(params, "team");
  const season = param(params, "season");
  const rawSort = param(params, "sort") ?? DEFAULT_SORT;
  const descending = rawSort.startsWith("-");
  const sortKey = oneOf(rawSort.replace(/^-/, ""), SORTS, "pts");
  const sort = `${descending ? "-" : ""}${sortKey}`;
  return {
    season: season && SEASON_LABEL.test(season) ? season : undefined,
    team: team && /^\d+$/.test(team) ? team : undefined,
    position: oneOf(param(params, "position"), ["G", "F", "C", ""] as const, "") || undefined,
    status: param(params, "status") === "all" ? "all" : undefined,
    sort: sort === DEFAULT_SORT ? undefined : sort,
    page: positiveInt(param(params, "page")),
    sortKey,
    descending,
  };
}
