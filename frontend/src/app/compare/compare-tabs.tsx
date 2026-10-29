import Link from "next/link";

import { cn } from "@/lib/utils";

const TABS = [
  { href: "/compare", label: "Players" },
  { href: "/compare/teams", label: "Teams" },
] as const;

export function CompareTabs({ current }: { current: (typeof TABS)[number]["href"] }) {
  return (
    <nav aria-label="Compare" className="mb-5 inline-flex rounded-full bg-muted p-1">
      {TABS.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          aria-current={tab.href === current ? "page" : undefined}
          className={cn(
            "inline-flex min-h-9 items-center rounded-full px-4 text-subhead transition-colors pointer-coarse:min-h-11",
            tab.href === current
              ? "bg-card font-semibold text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
