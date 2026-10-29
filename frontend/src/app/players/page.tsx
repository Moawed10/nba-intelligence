import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/data/page-header";
import { LoadingBlock } from "@/components/data/state-view";

import { Directory } from "./directory";
import { PlayerFinder } from "./player-finder";

export const metadata: Metadata = { title: "Players" };

export default function PlayersPage({ searchParams }: PageProps<"/players">) {
  return (
    <>
      <PageHeader
        title="Players"
        description="Search every player and explore season averages, trends and game logs."
      />
      <div className="space-y-10">
        <PlayerFinder />
        <Suspense fallback={<LoadingBlock label="Loading players" />}>
          <Directory searchParams={searchParams} />
        </Suspense>
      </div>
    </>
  );
}
