import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A titled module: an open section under a rule, not a box, so a page reads as one sheet. Headings are
 * real h2s so the page outline stays meaningful.
 */
export function Panel({
  id,
  kicker,
  title,
  actions,
  children,
  className,
  bodyClassName,
}: {
  id: string;
  kicker?: ReactNode;
  title: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  variant?: "open";
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={cn("rule-top flex min-w-0 flex-col", className)}>
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 pt-3 pb-5">
        <div className="min-w-0">
          {kicker && <p className="kicker mb-1.5">{kicker}</p>}
          <h2 id={`${id}-title`} className="headline text-[1.875rem]">
            {title}
          </h2>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      <div className={cn("min-w-0 flex-1", bodyClassName)}>{children}</div>
    </section>
  );
}
