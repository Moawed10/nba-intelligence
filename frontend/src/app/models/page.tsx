import type { Metadata } from "next";

import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "Models" };

export default function ModelsPage() {
  return (
    <>
      <PageHeader
        title="Models"
        description="How accurate the predictions are, measured on games the models never saw."
      />
      <NotConnected shows="measured error against a simple baseline, interval coverage and past predictions next to actual results" />
    </>
  );
}
