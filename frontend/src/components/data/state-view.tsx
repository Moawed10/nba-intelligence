"use client";

import { CircleAlert, Clock, Inbox, type LucideIcon, Wrench } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { describeError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type Kind = "empty" | "error" | "stale" | "unavailable";

const ICON: Record<Kind, LucideIcon> = {
  empty: Inbox,
  error: CircleAlert,
  stale: Clock,
  unavailable: Wrench,
};

interface StateViewProps {
  kind: Kind;
  title?: string;
  message?: ReactNode;
  error?: unknown;
  action?: ReactNode;
  onRetry?: () => void;
  className?: string;
}

/** The one place empty, error, stale and unavailable states are rendered. */
export function StateView({ kind, title, message, error, action, onRetry, className }: StateViewProps) {
  const described = kind === "error" ? describeError(error) : null;
  const Icon = ICON[kind];
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl bg-card px-6 py-12 text-center",
        className,
      )}
    >
      <Icon
        aria-hidden
        className={cn("size-8", kind === "error" ? "text-negative" : "text-muted-foreground")}
      />
      <div className="max-w-md">
        <p className="text-headline font-semibold">{title ?? described?.title}</p>
        {(message ?? described?.message) && (
          <p className="mt-1 text-subhead text-muted-foreground">{message ?? described?.message}</p>
        )}
      </div>
      {(onRetry || action) && (
        <div className="mt-1 flex gap-2">
          {onRetry && (
            <Button variant="outline" onClick={onRetry}>
              Try again
            </Button>
          )}
          {action}
        </div>
      )}
    </div>
  );
}

/** Skeleton sized like the content it replaces, so loading does not shift layout. */
export function LoadingBlock({ label, className }: { label: string; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={cn("space-y-3", className)}>
      <span className="sr-only">{label}</span>
      <Skeleton className="h-6 w-1/3 rounded-md" />
      <Skeleton className="h-32 w-full rounded-xl" />
    </div>
  );
}
