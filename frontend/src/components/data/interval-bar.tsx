import { formatStat } from "@/lib/format";

interface IntervalBarProps {
  label: string;
  point: number;
  lower: number;
  upper: number;
  /** e.g. 0.8 for an 80% interval */
  level: number;
  /** Axis maximum, so bars for the same stat share a scale. */
  max: number;
}

/** A prediction with its likely range, drawn and stated in text. */
export function IntervalBar({ label, point, lower, upper, level, max }: IntervalBarProps) {
  const pct = (v: number) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
  const levelText = `${Math.round(level * 100)}%`;
  const summary = `${label}: predicted ${formatStat(point)}, likely range ${formatStat(lower)} to ${formatStat(upper)} (${levelText} interval)`;
  return (
    <figure className="space-y-2">
      <figcaption className="flex items-baseline justify-between gap-3">
        <span className="text-subhead text-muted-foreground">{label}</span>
        <span className="tabular-nums">
          <span className="text-title2 font-semibold">{formatStat(point)}</span>
          <span className="ml-2 text-footnote text-muted-foreground">
            likely {formatStat(lower)}–{formatStat(upper)} ({levelText})
          </span>
        </span>
      </figcaption>
      <div role="img" aria-label={summary} className="relative h-2 rounded-full bg-muted">
        <div
          className="absolute inset-y-0 rounded-full bg-predicted/30"
          style={{ left: pct(lower), width: `calc(${pct(upper)} - ${pct(lower)})` }}
        />
        <div
          className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-predicted"
          style={{ left: pct(point) }}
        />
      </div>
    </figure>
  );
}
