import type { ReactNode } from "react";

export function PageHeader({
  title,
  kicker,
  description,
  actions,
}: {
  title: string;
  kicker?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {kicker && <p className="kicker mb-2 text-primary">{kicker}</p>}
        <h1
          tabIndex={-1}
          className="text-[2.5rem] leading-none font-extrabold outline-none sm:text-large-title"
        >
          {title}
        </h1>
        {description && <p className="mt-2 text-body text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
