"use client";

import { animate, useMotionValue, useReducedMotion, useTransform, motion } from "motion/react";
import { useEffect } from "react";

import { formatSigned, formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

interface StatTileProps {
  label: string;
  value: number | null;
  unit?: string;
  /** Change versus a reference, e.g. last 5 vs season. Shown with an arrow and words, not color alone. */
  delta?: { value: number; versus: string } | null;
  footnote?: string;
  className?: string;
}

function AnimatedNumber({ value }: { value: number }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const text = useTransform(mv, (v) => formatStat(v));
  useEffect(() => {
    if (reduce) {
      mv.set(value);
      return;
    }
    const controls = animate(mv, value, { duration: 0.4, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [value, reduce, mv]);
  return <motion.span>{text}</motion.span>;
}

export function StatTile({ label, value, unit, delta, footnote, className }: StatTileProps) {
  const direction = delta ? (delta.value > 0 ? "up" : delta.value < 0 ? "down" : "flat") : null;
  return (
    <div className={cn("rounded-xl bg-card p-4", className)}>
      <dt className="text-footnote font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1">
        <span className="text-stat font-semibold tabular-nums tracking-tight">
          {value == null ? "—" : <AnimatedNumber value={value} />}
        </span>
        {unit && value != null && (
          <span className="ml-1 text-subhead text-muted-foreground">{unit}</span>
        )}
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
