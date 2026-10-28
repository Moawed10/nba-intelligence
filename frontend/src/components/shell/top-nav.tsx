"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { BrandMark } from "./brand-mark";
import { MoreMenu } from "./more-menu";
import { isActive, PRIMARY_NAV } from "./nav-config";
import { ThemeToggle } from "./theme-toggle";

export function TopNav() {
  const pathname = usePathname();
  return (
    <header className="material-nav sticky top-0 z-40 border-b border-border/70">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="flex min-h-11 items-center gap-2 text-headline font-semibold tracking-tight"
        >
          <BrandMark />
          <span>NBA Intelligence</span>
        </Link>

        <nav aria-label="Primary" className="mx-auto hidden md:block">
          <ul className="flex items-center gap-1">
            {PRIMARY_NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-9 items-center rounded-full px-3.5 text-subhead transition-colors",
                      active
                        ? "font-semibold text-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {active && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-0 -z-10 rounded-full bg-muted"
                        transition={{ type: "spring", stiffness: 420, damping: 38 }}
                      />
                    )}
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <MoreMenu />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
