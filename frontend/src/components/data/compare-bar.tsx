import { cn } from "@/lib/utils";

interface CompareBarProps {
  label: string;
  left: number | null;
  right: number | null;
  format: (value: number | null) => string;
  /** Which direction is better for this statistic; decides the highlighted side. */
  better?: "higher" | "lower";
}

/** Two values on a shared scale, mirrored from the centre. The leader is stated in text too. */
export function CompareBar({ label, left, right, format, better = "higher" }: CompareBarProps) {
  const max = Math.max(left ?? 0, right ?? 0) || 1;
  const winner =
    left == null || right == null || left === right
      ? null
      : (better === "higher") === left > right
        ? "left"
        : "right";
  const width = (value: number | null) => `${((value ?? 0) / max) * 100}%`;
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-x-3 gap-y-1">
      <span
        className={cn(
          "text-right text-headline tabular-nums",
          winner === "left" ? "font-semibold text-foreground" : "text-muted-foreground",
        )}
      >
        {format(left)}
      </span>
      <span className="text-center text-footnote text-muted-foreground">
        {label}
        {winner && <span className="sr-only">, {winner === "left" ? "first" : "second"} player leads</span>}
      </span>
      <span
        className={cn(
          "text-headline tabular-nums",
          winner === "right" ? "font-semibold text-foreground" : "text-muted-foreground",
        )}
      >
        {format(right)}
      </span>
      <div aria-hidden className="flex h-1.5 justify-end overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            winner === "left" ? "bg-primary" : "bg-chart-3",
          )}
          style={{ width: width(left) }}
        />
      </div>
      <span aria-hidden />
      <div aria-hidden className="flex h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            winner === "right" ? "bg-primary" : "bg-chart-3",
          )}
          style={{ width: width(right) }}
        />
      </div>
    </div>
  );
}
