"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, Suspense } from "react";

type Render = (pathname: string | null) => ReactNode;

function PathnameReader({ children }: { children: Render }) {
  return children(usePathname());
}

/**
 * Reads the pathname inside its own Suspense boundary. On routes with dynamic params the pathname is
 * unknown while Next.js prerenders the shell, so the fallback renders with no active item.
 */
export function WithPathname({ children }: { children: Render }) {
  return (
    <Suspense fallback={children(null)}>
      <PathnameReader>{children}</PathnameReader>
    </Suspense>
  );
}
