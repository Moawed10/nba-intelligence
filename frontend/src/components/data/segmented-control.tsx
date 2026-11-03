"use client";

import { motion } from "motion/react";
import { type KeyboardEvent, useId, useRef } from "react";

import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface Segment<T extends string> {
  value: T;
  label: string;
}

interface SegmentedControlProps<T extends string> {
  label: string;
  segments: Segment<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

/** Radio-group semantics with roving tabindex: one Tab stop, arrow keys move and select. */
export function SegmentedControl<T extends string>({
  label,
  segments,
  value,
  onChange,
  className,
}: SegmentedControlProps<T>) {
  const id = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent, index: number) {
    const last = segments.length - 1;
    const target =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? index === last
          ? 0
          : index + 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? index === 0
            ? last
            : index - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (target === null) return;
    event.preventDefault();
    onChange(segments[target].value);
    refs.current[target]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn("inline-flex rounded-full bg-muted p-0.5", className)}
    >
      {segments.map((segment, index) => {
        const selected = segment.value === value;
        return (
          <button
            key={segment.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(segment.value)}
            onKeyDown={(e) => onKeyDown(e, index)}
            className={cn(
              "relative min-h-9 shrink-0 rounded-full px-2.5 sm:px-3.5 text-subhead whitespace-nowrap transition-colors duration-150 active:opacity-70 pointer-coarse:min-h-11",
              selected ? "font-semibold text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {selected && (
              <motion.span
                layoutId={`segment-${id}`}
                className="absolute inset-0 rounded-full bg-thumb shadow-raised"
                transition={SPRING.snappy}
              />
            )}
            <span className="relative">{segment.label}</span>
          </button>
        );
      })}
    </div>
  );
}
