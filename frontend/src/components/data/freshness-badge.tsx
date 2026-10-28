import { formatGameTime, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export type FreshnessStatus = "fresh" | "aging" | "stale" | "unavailable";

const DOT: Record<FreshnessStatus, string> = {
  fresh: "bg-positive",
  aging: "bg-primary",
  stale: "bg-negative",
  unavailable: "bg-muted-foreground",
};

export function freshnessLabel(status: FreshnessStatus, lastSync: string | null, now?: Date) {
  if (!lastSync || status === "unavailable") {
    return lastSync
      ? `Data temporarily unavailable · showing data through ${formatGameTime(lastSync)}`
      : "Data not yet available";
  }
  const when = formatRelativeTime(lastSync, now);
  return status === "stale" ? `Last updated ${when} · may be out of date` : `Updated ${when}`;
}

export function FreshnessBadge({
  status,
  lastSync,
  className,
}: {
  status: FreshnessStatus;
  lastSync: string | null;
  className?: string;
}) {
  return (
    <p className={cn("inline-flex items-center gap-2 text-footnote text-muted-foreground", className)}>
      <span aria-hidden className={cn("size-1.5 rounded-full", DOT[status])} />
      {lastSync ? (
        <time dateTime={lastSync}>{freshnessLabel(status, lastSync)}</time>
      ) : (
        freshnessLabel(status, lastSync)
      )}
    </p>
  );
}
