"use client";

import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect } from "react";

import { DURATION, EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Renders the value at once and tweens only when it later changes; never counts up on load. */
export function AnimatedNumber({
  value,
  format,
}: {
  value: number;
  format: (value: number) => string;
}) {
  const reduce = useReducedMotion();
  const current = useMotionValue(value);
  const text = useTransform(current, format);
  useEffect(() => {
    if (reduce) {
      current.set(value);
      return;
    }
    const controls = animate(current, value, { duration: DURATION.data, ease: EASE_OUT });
    return () => controls.stop();
  }, [value, reduce, current]);
  return <motion.span>{text}</motion.span>;
}

/** A large scoreboard number. Assistive technology always reads the real value. */
export function Numeral({
  value,
  decimals = 0,
  className,
}: {
  value: number;
  decimals?: number;
  className?: string;
}) {
  return (
    <span className={cn("numeral", className)}>
      <span className="sr-only">{value.toFixed(decimals)}</span>
      <span aria-hidden>
        <AnimatedNumber value={value} format={(v) => v.toFixed(decimals)} />
      </span>
    </span>
  );
}
