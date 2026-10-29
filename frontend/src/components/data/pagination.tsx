import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { formatCount } from "@/lib/format";

interface PaginationProps {
  label: string;
  page: number;
  pages: number;
  total: number;
  href: (page: number) => string;
}

const LINK =
  "inline-flex min-h-11 items-center gap-1 rounded-lg px-3 text-subhead font-medium text-primary hover:bg-muted";

export function Pagination({ label, page, pages, total, href }: PaginationProps) {
  if (pages <= 1) return null;
  return (
    <nav aria-label={label} className="flex items-center justify-between gap-3 pt-4">
      <div className="min-w-24">
        {page > 1 && (
          <Link href={href(page - 1)} scroll={false} aria-label="Previous page" className={LINK}>
            <ChevronLeft aria-hidden className="size-4" />
            Previous
          </Link>
        )}
      </div>
      <p className="text-center text-footnote text-muted-foreground tabular-nums">
        Page {page} of {pages} · {formatCount(total)} total
      </p>
      <div className="flex min-w-24 justify-end">
        {page < pages && (
          <Link href={href(page + 1)} scroll={false} aria-label="Next page" className={LINK}>
            Next
            <ChevronRight aria-hidden className="size-4" />
          </Link>
        )}
      </div>
    </nav>
  );
}
