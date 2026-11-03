"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

export interface Column<Row> {
  key: string;
  header: string;
  /** Full name for abbreviations, exposed to assistive tech and as a tooltip. */
  description?: string;
  cell: (row: Row) => ReactNode;
  sortValue?: (row: Row) => number | string | null;
  numeric?: boolean;
}

interface DataTableProps<Row> {
  caption: string;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  initialSort?: { key: string; direction: "ascending" | "descending" };
  /** A summary row (e.g. career totals) kept below the sorted rows. */
  footer?: Row;
}

/** A real <table>: sticky first column and a labelled, focusable scroll region on narrow screens. */
export function DataTable<Row>({ caption, columns, rows, rowKey, initialSort, footer }: DataTableProps<Row>) {
  const [sort, setSort] = useState(initialSort);

  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sort?.key);
    if (!sort || !column?.sortValue) return rows;
    const factor = sort.direction === "ascending" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (av == null) return 1;
      if (bv == null) return -1;
      return av < bv ? -factor : av > bv ? factor : 0;
    });
  }, [rows, columns, sort]);

  return (
    <div role="region" aria-label={caption} tabIndex={0} className="scroll-quiet relative overflow-x-auto">
      <table className="w-full border-collapse text-subhead">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border">
            {columns.map((column, i) => {
              const active = sort?.key === column.key;
              const Icon = !active ? ArrowUpDown : sort.direction === "ascending" ? ArrowUp : ArrowDown;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={active ? sort.direction : undefined}
                  title={column.description}
                  className={cn(
                    "kicker whitespace-nowrap px-3 py-2",
                    column.numeric ? "text-right" : "text-left",
                    i === 0 && "sticky left-0 z-10 bg-cell shadow-[inset_0_-1px_0_var(--border)]",
                  )}
                >
                  {column.sortValue ? (
                    <button
                      type="button"
                      onClick={() =>
                        setSort({
                          key: column.key,
                          direction: active && sort.direction === "descending" ? "ascending" : "descending",
                        })
                      }
                      className={cn(
                        "inline-flex min-h-8 items-center gap-1 transition-colors duration-150 hover:text-foreground pointer-coarse:min-h-11",
                        active && "text-primary",
                      )}
                    >
                      {column.header}
                      {column.description && <span className="sr-only">, {column.description}</span>}
                      <Icon aria-hidden className="size-3.5" />
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={rowKey(row)} className="border-b border-border/60 transition-colors duration-150 last:border-0 hover:bg-muted/40">
              {columns.map((column, i) => {
                const Cell = i === 0 ? "th" : "td";
                return (
                  <Cell
                    key={column.key}
                    scope={i === 0 ? "row" : undefined}
                    className={cn(
                      "whitespace-nowrap px-3 py-2 font-normal",
                      column.numeric ? "text-right tabular-nums" : "text-left",
                      i === 0 && "sticky left-0 bg-cell",
                    )}
                  >
                    {column.cell(row)}
                  </Cell>
                );
              })}
            </tr>
          ))}
        </tbody>
        {footer && (
          <tfoot>
            <tr className="border-t-2 border-border font-semibold">
              {columns.map((column, i) => {
                const Cell = i === 0 ? "th" : "td";
                return (
                  <Cell
                    key={column.key}
                    scope={i === 0 ? "row" : undefined}
                    className={cn(
                      "whitespace-nowrap px-3 py-2.5",
                      column.numeric ? "text-right tabular-nums" : "text-left",
                      i === 0 && "sticky left-0 bg-cell",
                    )}
                  >
                    {column.cell(footer)}
                  </Cell>
                );
              })}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
