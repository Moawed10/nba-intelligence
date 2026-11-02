import {
  CalendarX2,
  CircleAlert,
  Clock,
  Cpu,
  Hourglass,
  Inbox,
  type LucideIcon,
  Plug,
  WifiOff,
} from "lucide-react";
import type { ReactNode } from "react";

import type { ApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

export type UnavailableKind =
  "empty" | "no_games" | "stale" | "not_built" | "no_model" | "error" | "rate_limited" | "offline";

const ICON: Record<UnavailableKind, LucideIcon> = {
  empty: Inbox,
  no_games: CalendarX2,
  stale: Clock,
  not_built: Plug,
  no_model: Cpu,
  error: CircleAlert,
  rate_limited: Hourglass,
  offline: WifiOff,
};

/** Maps an API failure to the state the user should see. */
export function kindForError(error: ApiError): UnavailableKind {
  if (error.status === 0) return "offline";
  if (error.status === 429) return "rate_limited";
  if (error.code === "model_unavailable") return "no_model";
  return "error";
}

/** A compact, specific explanation that sits inside the module it replaces. */
export function Unavailable({
  kind,
  title,
  children,
  action,
  className,
}: {
  kind: UnavailableKind;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const Icon = ICON[kind];
  const alert = kind === "error" || kind === "offline";
  return (
    <div
      role={alert ? "alert" : "status"}
      className={cn(
        "flex items-start gap-3 rounded-lg border border-border bg-muted/40 px-4 py-3.5",
        className,
      )}
    >
      <Icon
        aria-hidden
        className={cn("mt-0.5 size-4 shrink-0", alert ? "text-negative" : "text-muted-foreground")}
      />
      <div className="min-w-0 text-subhead">
        <p className="font-medium">{title}</p>
        {children && <div className="mt-0.5 text-muted-foreground">{children}</div>}
        {action && <div className="mt-2">{action}</div>}
      </div>
    </div>
  );
}
