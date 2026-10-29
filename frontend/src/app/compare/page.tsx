import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/data/page-header";
import { LoadingBlock } from "@/components/data/state-view";

import { CompareView } from "./compare";

export const metadata: Metadata = { title: "Compare" };

export default function ComparePage({ searchParams }: PageProps<"/compare">) {
  return (
    <>
      <PageHeader
        kicker="Head to head"
        title="Compare"
        description="Two players, the same season, the same definitions."
      />
      <Suspense fallback={<LoadingBlock label="Loading comparison" className="panel p-5" />}>
        <CompareView searchParams={searchParams} />
      </Suspense>
    </>
  );
}
