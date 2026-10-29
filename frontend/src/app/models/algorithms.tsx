"use client";

import { useState } from "react";

import { SegmentedControl } from "@/components/data/segmented-control";
import type { AlgorithmMetrics } from "@/lib/api/types";
import { algorithmLabel, TARGET_ORDER, targetLabel } from "@/lib/models";
import { cn } from "@/lib/utils";

const SHORT: Record<string, string> = {
  pts: "PTS",
  reb: "REB",
  ast: "AST",
  fg3m: "3PM",
  stl: "STL",
  blk: "BLK",
  min: "MIN",
};

/** Every candidate algorithm per statistic, ranked by validation error, the number selection used. */
export function AlgorithmComparison({
  algorithms,
  testSeason,
}: {
  algorithms: AlgorithmMetrics[];
  testSeason: string;
}) {
  const targets = TARGET_ORDER.filter((t) => algorithms.some((a) => a.target === t));
  const [target, setTarget] = useState<string>(targets[0]);
  const rows = algorithms
    .filter((a) => a.target === target)
    .sort((a, b) => (a.validation_mae ?? Infinity) - (b.validation_mae ?? Infinity));
  const baseline = rows.find((r) => r.algorithm === "rolling_baseline");
  const gain = (mae: number | null) =>
    baseline?.validation_mae && mae != null
      ? (baseline.validation_mae - mae) / baseline.validation_mae
      : null;
  const maxGain = Math.max(0.0001, ...rows.map((r) => Math.abs(gain(r.validation_mae) ?? 0)));

  return (
    <div className="space-y-4">
      <div className="-mx-1 overflow-x-auto px-1">
        <SegmentedControl
          label="Statistic"
          value={target}
          onChange={setTarget}
          segments={targets.map((t) => ({ value: t, label: SHORT[t] ?? t }))}
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[30rem] text-subhead tabular-nums">
          <caption className="sr-only">
            {targetLabel(target)}: mean absolute error of each algorithm on the validation season and on{" "}
            {testSeason}, with the improvement over the baseline
          </caption>
          <thead className="text-footnote text-muted-foreground">
            <tr className="border-b border-border">
              <th scope="col" className="py-2 text-left font-medium">
                Algorithm
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                Validation error
              </th>
              <th scope="col" className="w-32 py-2 pl-4 text-left font-medium">
                Improvement
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                {testSeason} error
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                R²
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const g = gain(row.validation_mae);
              return (
                <tr
                  key={row.algorithm}
                  className={cn("border-b border-border/50 last:border-0", row.selected && "bg-primary/5")}
                >
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    <span className={cn(row.selected && "font-semibold")}>
                      {algorithmLabel(row.algorithm)}
                    </span>
                    {row.selected && (
                      <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-footnote font-medium text-primary-foreground">
                        Selected
                      </span>
                    )}
                  </th>
                  <td className="py-2 text-right">{row.validation_mae?.toFixed(3) ?? "—"}</td>
                  <td className="py-2 pl-4">
                    {row.algorithm === "rolling_baseline" ? (
                      <span className="text-footnote text-muted-foreground">Reference</span>
                    ) : g == null ? (
                      "—"
                    ) : (
                      <span className="flex items-center gap-2">
                        <span
                          aria-hidden
                          className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
                        >
                          <span
                            className={cn(
                              "absolute inset-y-0 left-0 rounded-full",
                              g > 0 ? "bg-positive" : "bg-negative",
                            )}
                            style={{ width: `${(Math.abs(g) / maxGain) * 100}%` }}
                          />
                        </span>
                        <span
                          className={cn(
                            "w-14 text-right text-footnote",
                            g > 0 ? "text-positive" : "text-negative",
                          )}
                        >
                          {(g * 100).toFixed(1)}%
                        </span>
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right">{row.test_mae?.toFixed(3) ?? "—"}</td>
                  <td className="py-2 text-right text-muted-foreground">{row.test_r2?.toFixed(2) ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-footnote text-muted-foreground">
        The algorithm with the lowest validation error is selected; {testSeason} error is reported afterwards
        and never used to choose. Improvement is how much smaller the average miss is than the baseline&apos;s
        on the validation season.
      </p>
    </div>
  );
}
