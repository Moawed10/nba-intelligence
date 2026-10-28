import { NotConnected } from "@/components/data/not-connected";
import { PageHeader } from "@/components/data/page-header";

export default function OverviewPage() {
  return (
    <>
      <PageHeader
        title="Overview"
        description="Today's matchups, standout performances and how the models are doing."
      />
      <NotConnected shows="upcoming games, recent standout lines and current model accuracy" />
    </>
  );
}
