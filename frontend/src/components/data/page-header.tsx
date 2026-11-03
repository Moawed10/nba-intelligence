import type { ReactNode } from "react";

export function PageHeader({
  title,
  kicker,
  description,
  actions,
  compact,
}: {
  title: string;
  kicker?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** A one-line header for pages whose feature section holds the focal point. */
  compact?: boolean;
}) {
  return (
    <div
      className={
        compact
          ? "flex flex-wrap items-center justify-between gap-x-6 gap-y-3 pb-5"
          : "flex flex-col gap-3 pt-2 pb-9 sm:flex-row sm:items-end sm:justify-between sm:pt-6"
      }
    >
      <div className="max-w-3xl">
        {kicker && <p className="kicker mb-2.5 text-primary">{kicker}</p>}
        <h1
          tabIndex={-1}
          className={
            compact
              ? "text-[2.5rem] leading-none outline-none"
              : "text-[clamp(3rem,7vw,5rem)] leading-[0.98] outline-none"
          }
        >
          {title}
        </h1>
        {description && <p className="mt-4 text-title3 text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 max-sm:w-full">{actions}</div>}
    </div>
  );
}
