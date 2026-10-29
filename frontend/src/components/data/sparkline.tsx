import { cn } from "@/lib/utils";

/** A tiny trend line. Decorative: callers state the same values in text. */
export function Sparkline({
  values,
  reference,
  width = 96,
  height = 28,
  className,
}: {
  values: number[];
  reference?: number | null;
  width?: number;
  height?: number;
  className?: string;
}) {
  if (values.length < 2) return null;
  const all = reference != null ? [...values, reference] : values;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const x = (i: number) => (i / (values.length - 1)) * (width - 4) + 2;
  const y = (v: number) => height - 3 - ((v - min) / span) * (height - 6);
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <svg
      aria-hidden
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
    >
      {reference != null && (
        <line
          x1="2"
          x2={width - 2}
          y1={y(reference)}
          y2={y(reference)}
          stroke="var(--muted-foreground)"
          strokeWidth="1"
          strokeDasharray="2 3"
          opacity="0.6"
        />
      )}
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r="2.5" fill="var(--primary)" />
    </svg>
  );
}
