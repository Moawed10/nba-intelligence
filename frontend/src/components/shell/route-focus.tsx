"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/** After client-side navigation, moves focus to the new page's h1 so screen readers announce it. */
export function RouteFocus() {
  const pathname = usePathname();
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    // Page headings carry tabIndex={-1} (PageHeader) so they can take focus without a Tab stop.
    document.querySelector<HTMLElement>("main h1")?.focus();
  }, [pathname]);

  return null;
}
