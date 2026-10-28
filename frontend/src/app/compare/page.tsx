import type { Metadata } from "next";

import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "Compare" };

export default function ComparePage() {
  return (
    <>
      <PageHeader
        title="Compare"
        description="Put two players side by side on the same season and the same definitions."
      />
      <NotConnected shows="side-by-side averages, efficiency and trends for two players" />
    </>
  );
}
