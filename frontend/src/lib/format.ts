const NUMBER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const INTEGER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const PERCENT = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });

/** Averages and predictions: one decimal. Missing values render as an em dash, never 0. */
export function formatStat(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "—" : NUMBER.format(value);
}

export function formatCount(value: number | null | undefined): string {
  return value == null ? "—" : INTEGER.format(value);
}

export function formatPercent(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "—" : PERCENT.format(value);
}

export function formatSigned(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "±";
  return `${sign}${NUMBER.format(Math.abs(rounded))}`;
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];
const RELATIVE = new Intl.RelativeTimeFormat("en-US", { numeric: "auto", style: "long" });

export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  if (Math.abs(seconds) < 60) return "just now";
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return RELATIVE.format(Math.trunc(seconds / size), unit);
  }
  return "just now";
}

const DATE_TIME = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "America/New_York",
  timeZoneName: "short",
});

export function formatGameTime(iso: string): string {
  return DATE_TIME.format(new Date(iso));
}

export function formatHeight(inches: number | null | undefined): string {
  return inches == null ? "—" : `${Math.floor(inches / 12)}′${inches % 12}″`;
}

const GAME_DATE = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const GAME_DATE_YEAR = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

/** Game dates are calendar dates (YYYY-MM-DD), so they are formatted in UTC to avoid shifting. */
export function formatGameDate(date: string, withYear = false): string {
  return (withYear ? GAME_DATE_YEAR : GAME_DATE).format(new Date(`${date}T00:00:00Z`));
}

/** A single game's value: whole numbers for counts, one decimal for minutes. */
export function formatGameValue(value: number | null | undefined): string {
  return value != null && Number.isInteger(value) ? formatCount(value) : formatStat(value);
}
