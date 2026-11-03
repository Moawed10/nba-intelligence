import { cn } from "@/lib/utils";

interface CompareBarProps {
  label: string;
  left: number | null;
  right: number | null;
  format: (value: number | null) => string;
  /** Which direction is better for this statistic; "neither" highlights no side (e.g. pace). */
  better?: "higher" | "lower" | "neither";
  /** Names announced to screen readers for the leading side. */
  names?: [string, string];
}

/** The leader's marker: a circle on the left, a diamond on the right, so it isn't color alone. */
function LeadMark({ className }: { className: string }) {
  return <span aria-hidden className={cn("inline-block size-1.5 align-[0.2em]", className)} />;
}

/** Two values on a shared scale, mirrored from the centre. The leader is stated in text too. */
export function CompareBar({
  label,
  left,
  right,
  format,
  better = "higher",
  names = ["First player", "Second player"],
}: CompareBarProps) {
  const max = Math.max(left ?? 0, right ?? 0) || 1;
  const winner =
    better === "neither" || left == null || right == null || left === right
      ? null
      : (better === "higher") === left > right
        ? "left"
        : "right";
  const width = (value: number | null) => `${((value ?? 0) / max) * 100}%`;
  const side = (value: number | null, which: "left" | "right") => (
    <div className={cn("min-w-0", which === "left" && "text-right")}>
      <span
        className={cn(
          "numeral text-title2",
          winner === which ? "text-foreground" : "font-semibold text-muted-foreground",
        )}
      >
        {winner === which && which === "left" && <LeadMark className="mr-1.5 rounded-full bg-chart-1" />}
        {format(value)}
        {winner === which && which === "right" && <LeadMark className="ml-1.5 rotate-45 bg-chart-2" />}
      </span>
      <div aria-hidden className={cn("mt-1 flex h-1 rounded-full bg-muted", which === "left" && "justify-end")}>
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-300",
            which === "left" ? "bg-chart-1" : "bg-chart-2",
            winner !== which && winner != null && "opacity-45",
          )}
          style={{ width: width(value) }}
        />
      </div>
    </div>
  );
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(5.5rem,auto)_minmax(0,1fr)] items-center gap-x-3 sm:grid-cols-[minmax(0,1fr)_9rem_minmax(0,1fr)]">
      {side(left, "left")}
      <span className="text-center text-footnote text-muted-foreground">
        {label}
        {winner && <span className="sr-only">, {names[winner === "left" ? 0 : 1]} leads</span>}
      </span>
      {side(right, "right")}
    </div>
  );
}
