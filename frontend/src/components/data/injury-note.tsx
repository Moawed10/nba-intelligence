import type { InjuryReport } from "@/lib/api/types";
import { roughReturn } from "@/lib/format";
import { cn } from "@/lib/utils";

/** "Left hip strain", or the bare status reason when the source gives no body part. */
export function injuryLabel(injury: InjuryReport): string {
  const words = [injury.side, injury.injury, injury.detail].filter(Boolean).join(" ").toLowerCase();
  return words ? words[0].toUpperCase() + words.slice(1) : "Reason not given";
}

export function isOut(injury: InjuryReport): boolean {
  return injury.status.toLowerCase() === "out";
}

/** The status as a labelled pill: the word carries the meaning, the color only reinforces it. */
export function InjuryStatus({ injury, className }: { injury: InjuryReport; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 py-0.5 font-mono text-[0.75rem] font-medium whitespace-nowrap text-foreground uppercase",
        isOut(injury) ? "border-negative" : "border-primary",
        className,
      )}
    >
      {injury.status}
    </span>
  );
}

export function ReturnEstimate({ injury }: { injury: InjuryReport }) {
  return <span suppressHydrationWarning>{roughReturn(injury.return_date) ?? "No return estimate"}</span>;
}
