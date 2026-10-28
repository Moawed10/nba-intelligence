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
