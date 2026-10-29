import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/data/page-header";
import { LoadingBlock } from "@/components/data/state-view";

import { PredictView } from "./predict";

export const metadata: Metadata = { title: "Predictions" };

export default function PredictPage({ searchParams }: PageProps<"/predict">) {
  return (
    <>
      <PageHeader
        kicker="Next game"
        title="Predictions"
        description="Pick a player and an upcoming game to see the forecast and what it draws on."
      />
      <Suspense fallback={<LoadingBlock label="Loading predictions" className="panel p-5" />}>
        <PredictView searchParams={searchParams} />
      </Suspense>
    </>
  );
}
