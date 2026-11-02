import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/data/page-header";
import { LoadingBlock } from "@/components/data/state-view";

import { ModelsView } from "./release";

export const metadata: Metadata = { title: "Models" };

export default function ModelsPage({ searchParams }: PageProps<"/models">) {
  return (
    <>
      <PageHeader
        kicker="How accurate"
        title="Models"
        description="How accurate the predictions are, measured on a season the models never saw."
      />
      <Suspense fallback={<LoadingBlock label="Loading model evaluation" className="panel p-5" />}>
        <ModelsView searchParams={searchParams} />
      </Suspense>
    </>
  );
}
