import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache, Suspense } from "react";

import { ApiErrorView } from "@/components/data/api-error";
import { PageHeader } from "@/components/data/page-header";
import { LiveRefresh } from "@/components/data/live-refresh";
import { LoadingBlock } from "@/components/data/state-view";
import { serverTry } from "@/lib/api/server";
import type { GameDetail } from "@/lib/api/types";
import { formatGameDate } from "@/lib/format";

import { GameMatchup } from "../../_overview/interactive";

const GAME_ID = /^\d{10}$/;
const SEASON_TYPE: Record<string, string> = {
  regular: "regular season",
  playin: "Play-In Tournament",
  playoffs: "playoffs",
};

const getGame = cache((id: string) => serverTry<GameDetail>(`/games/${id}`));

function title(game: GameDetail): string {
  return `${game.away.team.city} ${game.away.team.name} at ${game.home.team.city} ${game.home.team.name}`;
}

export async function generateMetadata({ params }: PageProps<"/games/[id]">): Promise<Metadata> {
  const { id } = await params;
  if (!GAME_ID.test(id)) return { title: "Game not found" };
  const { data } = await getGame(id);
  return {
    title: data ? `${data.away.team.abbreviation} at ${data.home.team.abbreviation} · Games` : "Games",
  };
}

async function GameView({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!GAME_ID.test(id)) notFound();
  const result = await getGame(id);
  if (result.error?.status === 404) notFound();
  if (result.error) return <ApiErrorView error={result.error} />;
  const game = result.data;
  return (
    <>
      <PageHeader
        compact
        kicker={`${game.season} ${SEASON_TYPE[game.season_type]}`}
        title={title(game)}
        description={`${formatGameDate(game.game_date, true)}${game.arena ? ` · ${game.arena}` : ""}`}
      />
      <LiveRefresh games={[game]} />
      <GameMatchup game={game} />
      <p className="mt-6 text-subhead">
        <Link href={`/games?date=${game.game_date}`} className="inline-flex items-center font-medium text-primary hover:underline pointer-coarse:min-h-11">
          All games on {formatGameDate(game.game_date, true)}
        </Link>
      </p>
    </>
  );
}

export default function GamePage({ params }: PageProps<"/games/[id]">) {
  return (
    <Suspense fallback={<LoadingBlock label="Loading game" />}>
      <GameView params={params} />
    </Suspense>
  );
}
