"use client";

import { motion } from "motion/react";
import Link from "next/link";

import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

import { BrandMark } from "./brand-mark";
import { CommandSearch } from "./command-search";
import { MoreMenu } from "./more-menu";
import { isActive, PRIMARY_NAV } from "./nav-config";
import { ThemeToggle } from "./theme-toggle";
import { WithPathname } from "./with-pathname";

export function TopNav() {
  return (
    <header className="material-nav sticky top-0 z-40 border-b border-border">
      <div className="mx-auto flex h-16 max-w-[84rem] items-center gap-2 px-4 sm:gap-3 sm:px-6 lg:gap-5 lg:px-8">
        <Link href="/" className="flex min-h-11 shrink-0 items-center gap-2">
          <BrandMark />
          {/* Wordmark only on phones and wide screens; at tablet width the five links need the room. */}
          <span className="display text-[1.1875rem] whitespace-nowrap max-[359px]:sr-only sm:text-[1.5rem] md:sr-only xl:not-sr-only">
            NBA Intelligence
          </span>
        </Link>

        <div className="ml-auto flex items-center md:ml-0 lg:w-72 xl:w-96">
          <CommandSearch />
        </div>

        <nav aria-label="Primary" className="hidden h-full md:ml-auto md:block">
          <WithPathname>
            {(pathname) => (
              <ul className="flex h-full items-stretch">
                {PRIMARY_NAV.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <li key={item.href} className="relative flex">
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex items-center px-2.5 text-subhead font-medium transition-colors duration-150 lg:px-3",
                          active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {item.label}
                      </Link>
                      {active && (
                        <motion.span
                          layoutId="nav-active"
                          className="absolute inset-x-2.5 -bottom-px h-0.5 bg-primary lg:inset-x-3"
                          transition={SPRING.snappy}
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </WithPathname>
        </nav>

        <div className="flex shrink-0 items-center gap-1">
          <WithPathname>{(pathname) => <MoreMenu pathname={pathname} />}</WithPathname>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
