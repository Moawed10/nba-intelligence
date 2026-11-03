"use client";

import { PageHeader } from "@/components/data/page-header";
import { StateView } from "@/components/data/state-view";

export default function PlayerError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <>
      <PageHeader title="Player" />
      <StateView
        kind="error"
        title="This profile couldn't load"
        message="Something went wrong on our side. Try again in a moment."
        onRetry={retry}
      />
    </>
  );
}
