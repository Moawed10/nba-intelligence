import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingBlock } from "@/components/data/state-view";

import { getProfile, PlayerProfileView } from "./profile";

export async function generateMetadata({ params }: PageProps<"/players/[id]">): Promise<Metadata> {
  const { id } = await params;
  if (!/^\d{1,10}$/.test(id)) return { title: "Player not found" };
  const { data } = await getProfile(id);
  return { title: data ? `${data.player.full_name} · Players` : "Players" };
}

export default function PlayerPage({ params, searchParams }: PageProps<"/players/[id]">) {
  return (
    <Suspense fallback={<LoadingBlock feature label="Loading player" className="pt-2" />}>
      <PlayerProfileView params={params} searchParams={searchParams} />
    </Suspense>
  );
}
