import type { Metadata } from "next";

import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "Games" };

export default function GamesPage() {
  return (
    <>
      <PageHeader title="Games" description="Schedule, results and box scores by date." />
      <NotConnected shows="the schedule and final box scores for any date" />
    </>
  );
}
