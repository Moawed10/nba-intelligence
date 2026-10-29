"use client";

import { motion } from "motion/react";
import Link from "next/link";

import { cn } from "@/lib/utils";

import { BrandMark } from "./brand-mark";
import { CommandSearch } from "./command-search";
import { MoreMenu } from "./more-menu";
import { isActive, PRIMARY_NAV } from "./nav-config";
import { ThemeToggle } from "./theme-toggle";
import { WithPathname } from "./with-pathname";

export function TopNav() {
  return (
    <header className="material-nav sticky top-0 z-40 border-b border-border/70">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6 lg:gap-4">
        <Link
          href="/"
          className="flex min-h-11 items-center gap-2 text-headline font-semibold tracking-tight"
        >
          <BrandMark />
          {/* Wordmark only on phones and wide screens; at tablet width the five links need the room. */}
          <span className="md:sr-only lg:not-sr-only">NBA Intelligence</span>
        </Link>

        <nav aria-label="Primary" className="mx-auto hidden md:block">
          <WithPathname>
            {(pathname) => (
              <ul className="flex items-center gap-1">
                {PRIMARY_NAV.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "relative flex h-9 items-center rounded-full px-2.5 text-subhead transition-colors lg:px-3.5",
                          active
                            ? "font-semibold text-foreground"
                            : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {active && (
                          <motion.span
                            layoutId="nav-active"
                            className="absolute inset-0 -z-10 rounded-full bg-muted"
                            transition={{
                              type: "spring",
                              stiffness: 420,
                              damping: 38,
                            }}
                          />
                        )}
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </WithPathname>
        </nav>

        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <CommandSearch />
          <WithPathname>{(pathname) => <MoreMenu pathname={pathname} />}</WithPathname>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
