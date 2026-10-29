"use client";

import { Ellipsis } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { isActive, SECONDARY_NAV } from "./nav-config";

export function MoreMenu({ pathname }: { pathname: string | null }) {
  // When an item navigates, focus belongs on the new page heading (RouteFocus), not the trigger.
  const navigated = useRef(false);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="More destinations" className="rounded-full">
          <Ellipsis aria-hidden className="size-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="min-w-44"
        onCloseAutoFocus={(event) => {
          if (navigated.current) event.preventDefault();
          navigated.current = false;
        }}
      >
        {SECONDARY_NAV.map(({ href, label, icon: Icon }) => (
          <DropdownMenuItem
            key={href}
            asChild
            className="min-h-10"
            onSelect={() => {
              navigated.current = href !== pathname;
            }}
          >
            <Link href={href} aria-current={isActive(pathname, href) ? "page" : undefined}>
              <Icon aria-hidden />
              {label}
            </Link>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
