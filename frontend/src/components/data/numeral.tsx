"use client";

import CountUp from "@/components/bits/count-up";
import { cn } from "@/lib/utils";

/**
 * A large scoreboard number that counts up once when it scrolls into view. Assistive technology
 * always reads the real value; the animated digits are decorative and skipped under reduced motion.
 */
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
        <CountUp to={value} decimals={decimals} duration={1.1} trigger="load" />
      </span>
    </span>
  );
}
