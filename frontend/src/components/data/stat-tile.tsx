"use client";

import { formatSigned, formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

import { AnimatedNumber } from "./numeral";

interface StatTileProps {
  label: string;
  value: number | null;
  unit?: string;
  /** Change versus a reference, e.g. last 5 vs season. Shown with an arrow and words, not color alone. */
  delta?: { value: number; versus: string } | null;
  footnote?: string;
  className?: string;
}

/** One cell of a stat-grid: label, big number, then context. */
export function StatTile({ label, value, unit, delta, footnote, className }: StatTileProps) {
  const shown = delta ? Math.round(delta.value * 10) / 10 : 0;
  const direction = delta ? (shown > 0 ? "up" : shown < 0 ? "down" : "flat") : null;
  return (
    <div className={cn("px-4 py-3.5", className)}>
      <dt className="kicker">{label}</dt>
      <dd className="mt-1.5">
        <span className="numeral text-[2.5rem]">
          {value == null ? "—" : <AnimatedNumber value={value} format={(v) => formatStat(v)} />}
        </span>
        {unit && value != null && <span className="ml-0.5 text-subhead text-muted-foreground">{unit}</span>}
        {value == null && <span className="sr-only">Not available</span>}
      </dd>
      {delta && (
        <dd
          className={cn(
            "mt-1 text-footnote tabular-nums",
            direction === "up" && "text-positive",
            direction === "down" && "text-negative",
            direction === "flat" && "text-muted-foreground",
          )}
        >
          <span aria-hidden>{direction === "up" ? "▲ " : direction === "down" ? "▼ " : "• "}</span>
          {formatSigned(delta.value)} vs {delta.versus}
        </dd>
      )}
      {footnote && <dd className="mt-1 text-footnote text-muted-foreground">{footnote}</dd>}
    </div>
  );
}
