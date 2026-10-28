"use client";

import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** Explains a term on click, tap or Enter; never hover-only. */
export function InfoHint({ term, children }: { term: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label={`What is ${term}?`}
        className="inline-flex size-6 items-center justify-center rounded-full align-middle text-muted-foreground hover:text-foreground pointer-coarse:size-11"
      >
        <Info aria-hidden className="size-4" />
      </PopoverTrigger>
      <PopoverContent className="max-w-xs text-subhead leading-relaxed">
        <p className="font-semibold">{term}</p>
        <div className="mt-1 text-muted-foreground">{children}</div>
      </PopoverContent>
    </Popover>
  );
}
