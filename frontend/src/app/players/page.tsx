import type { Metadata } from "next";

import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

import { PlayerFinder } from "./player-finder";

export const metadata: Metadata = { title: "Players" };

export default function PlayersPage() {
  return (
    <>
      <PageHeader
        title="Players"
        description="Search every player and explore season averages, trends and game logs."
      />
      <div className="space-y-8">
        <PlayerFinder />
        <NotConnected
          title="Player profiles aren't connected yet"
          shows="the full directory with team and position filters, and each player's profile"
        />
      </div>
    </>
  );
}
