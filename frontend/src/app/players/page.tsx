import type { Metadata } from "next";

import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "Players" };

export default function PlayersPage() {
  return (
    <>
      <PageHeader
        title="Players"
        description="Search every player and explore season averages, trends and game logs."
      />
      <NotConnected shows="a searchable directory of players with team and position filters" />
    </>
  );
}
