import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A titled analytical module. Headings are real h2s so the page outline stays meaningful. */
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
}) {
  return (
    <section aria-labelledby={`${id}-title`} className={cn("panel flex min-w-0 flex-col", className)}>
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-border px-4 pt-4 pb-3 sm:px-5">
        <div className="min-w-0">
          {kicker && <p className="kicker mb-1">{kicker}</p>}
          <h2 id={`${id}-title`} className="text-headline font-semibold">
            {title}
          </h2>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      <div className={cn("min-w-0 flex-1 p-4 sm:p-5", bodyClassName)}>{children}</div>
    </section>
  );
}
