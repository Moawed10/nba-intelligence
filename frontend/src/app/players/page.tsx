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
        kicker="Scouting"
        title="Players"
        description="Search any player, sort the league by what matters, and open a full scouting report."
      />
      <div className="space-y-6">
        <PlayerFinder />
        <Suspense fallback={<LoadingBlock label="Loading players" className="panel p-5" />}>
          <Directory searchParams={searchParams} />
        </Suspense>
      </div>
    </>
  );
}
