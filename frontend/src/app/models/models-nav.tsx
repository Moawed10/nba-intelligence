"use client";

import {
  Activity01Icon,
  ChartBarLineIcon,
  ChartHistogramIcon,
  ChartScatterIcon,
  DatabaseIcon,
  GitBranchIcon,
  Layers01Icon,
  PercentCircleIcon,
  Search01Icon,
  Target02Icon,
} from "@hugeicons/core-free-icons";

import BranchedMenu, { type BranchedMenuItem } from "@/components/bits/branched-menu";

const SECTIONS: BranchedMenuItem[] = [
  {
    label: "Evaluation",
    children: [
      { value: "release", label: "Release", icon: GitBranchIcon },
      { value: "accuracy", label: "Accuracy", icon: Target02Icon },
      { value: "algorithms", label: "Models compared", icon: ChartBarLineIcon },
      { value: "ranges", label: "Prediction ranges", icon: ChartHistogramIcon },
      { value: "check", label: "Check the predictions", icon: ChartScatterIcon },
      { value: "explorer", label: "Prediction history", icon: Search01Icon },
    ],
  },
  {
    label: "After release",
    children: [
      { value: "live", label: "Live accuracy", icon: Activity01Icon },
      { value: "double-double", label: "Double-double", icon: PercentCircleIcon },
      { value: "inputs", label: "Model inputs", icon: Layers01Icon },
      { value: "history", label: "Releases", icon: DatabaseIcon },
    ],
  },
];

/** Jumps between the evaluation panels on wide screens; every panel is also reachable by scrolling. */
export function ModelsNav() {
  return (
    <div className="sticky top-24">
      <p className="kicker mb-3">On this page</p>
      <BranchedMenu
        items={SECTIONS}
        defaultOpen={[0, 1]}
        defaultActive="release"
        onSelect={(value) => {
          const heading = document.getElementById(`${value}-title`);
          heading?.scrollIntoView({
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
            block: "start",
          });
        }}
        color="var(--foreground)"
        accentColor="var(--primary)"
        lineColor="var(--border)"
        width={220}
        rowHeight={34}
      />
    </div>
  );
}
