"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";

import { isActive, PRIMARY_NAV } from "./nav-config";
import { WithPathname } from "./with-pathname";

/** Bottom tab bar below 768px, mirroring iOS: five destinations, labels always visible. */
export function TabBar() {
  return (
    <nav
      aria-label="Primary"
      className="material-nav fixed inset-x-0 bottom-0 z-40 border-t border-border pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <WithPathname>
        {(pathname) => (
          <ul className="mx-auto grid max-w-lg grid-cols-5">
            {PRIMARY_NAV.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex min-h-14 flex-col items-center justify-center gap-0.5 text-[0.75rem] leading-tight transition-colors duration-150",
                      active ? "font-semibold text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {active && (
                      <span aria-hidden className="absolute inset-x-5 -top-px h-0.5 rounded-full bg-primary" />
                    )}
                    <Icon
                      aria-hidden
                      className={cn("size-5", active && "text-primary")}
                      strokeWidth={active ? 2.4 : 1.8}
                    />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </WithPathname>
    </nav>
  );
}
