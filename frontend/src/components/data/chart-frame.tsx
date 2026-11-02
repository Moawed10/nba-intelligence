"use client";

import { type ReactNode, useId, useState } from "react";

import { SegmentedControl } from "./segmented-control";

interface ChartFrameProps {
  title: string;
  /** Units of the y-axis, stated in text, e.g. "Points per game". */
  unit: string;
  /** One sentence that conveys the chart's main finding without interacting with it. */
  summary: string;
  chart: ReactNode;
  table: ReactNode;
  actions?: ReactNode;
  /** 3 when the chart sits inside a panel that already has a level-2 heading. */
  headingLevel?: 2 | 3;
}

/** Every chart ships with a title, units, a text summary and an equivalent table. */
export function ChartFrame({
  title,
  unit,
  summary,
  chart,
  table,
  actions,
  headingLevel = 2,
}: ChartFrameProps) {
  const Heading = headingLevel === 3 ? "h3" : "h2";
  const [view, setView] = useState<"chart" | "table">("chart");
  const headingId = useId();
  const summaryId = useId();
  return (
    <section aria-labelledby={headingId} className="rounded-xl bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Heading id={headingId} className="text-headline font-semibold">
            {title}
          </Heading>
          <p className="text-footnote text-muted-foreground">{unit}</p>
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <SegmentedControl
            label={`${title} view`}
            value={view}
            onChange={setView}
            segments={[
              { value: "chart", label: "Chart" },
              { value: "table", label: "Table" },
            ]}
          />
        </div>
      </div>
      <p id={summaryId} className="mt-3 text-subhead">
        {summary}
      </p>
      <div className="mt-4">
        {view === "chart" ? (
          <div role="figure" aria-label={title} aria-describedby={summaryId}>
            {chart}
          </div>
        ) : (
          table
        )}
      </div>
    </section>
  );
}
