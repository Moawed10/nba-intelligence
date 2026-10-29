"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const STREAMED_HEADING_WAIT_MS = 5000;

/** After client-side navigation, moves focus to the new page's h1 so screen readers announce it. */
export function RouteFocus() {
  const pathname = usePathname();
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    // The pathname changes before the new page commits, and data pages stream their heading in
    // later, so keep following the current h1 until the page settles. Page headings carry
    // tabIndex={-1} (PageHeader) so they can take focus without becoming a Tab stop.
    let focused: HTMLElement | null = null;
    const follow = () => {
      const heading = document.querySelector<HTMLElement>("main h1");
      if (!heading || heading === focused) return;
      const active = document.activeElement;
      const userMovedFocus = focused != null && active != null && active !== document.body && active !== focused;
      if (userMovedFocus) return;
      heading.focus();
      focused = heading;
    };
    follow();
    const observer = new MutationObserver(follow);
    const main = document.querySelector("main");
    if (main) observer.observe(main, { childList: true, subtree: true });
    const timeout = setTimeout(() => observer.disconnect(), STREAMED_HEADING_WAIT_MS);
    return () => {
      observer.disconnect();
      clearTimeout(timeout);
    };
  }, [pathname]);

  return null;
}
