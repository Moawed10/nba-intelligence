import type { Metadata } from "next";

import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "Predictions" };

export default function PredictPage() {
  return (
    <>
      <PageHeader
        title="Predictions"
        description="Pick a player and an upcoming game to see a forecast with its likely range."
      />
      <NotConnected shows="next-game predictions for points, rebounds, assists and more, each with an 80% range and the factors behind it" />
    </>
  );
}
