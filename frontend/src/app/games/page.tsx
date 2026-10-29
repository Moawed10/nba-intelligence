import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiErrorView } from "@/components/data/api-error";
import { PageHeader } from "@/components/data/page-header";
import { Panel } from "@/components/data/panel";
import { LoadingBlock } from "@/components/data/state-view";
import { serverTry } from "@/lib/api/server";
import type { GamePage } from "@/lib/api/types";
import { param, type SearchParams } from "@/lib/url";

import { ScheduleBoard } from "../_overview/interactive";

export const metadata: Metadata = { title: "Games" };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The NBA schedules by US Eastern date. */
const easternToday = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());

async function GamesView({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const requested = param(await searchParams, "date");
  await connection();
  const date =
    requested && ISO_DATE.test(requested) && !Number.isNaN(Date.parse(requested))
      ? requested
      : easternToday();
  const result = await serverTry<GamePage>("/games", { date_from: date, date_to: date, limit: 20 });
  if (result.error) return <ApiErrorView error={result.error} />;
  return (
    <Panel id="schedule" kicker="Schedule and results" title="Games by date">
      <ScheduleBoard initialDate={date} initialGames={result.data.items} fullBox urlPath="/games" />
    </Panel>
  );
}

export default function GamesPage({ searchParams }: PageProps<"/games">) {
  return (
    <>
      <PageHeader
        kicker="League"
        title="Games"
        description="Schedule, results and full box scores for any date since 2018-19."
      />
      <Suspense fallback={<LoadingBlock label="Loading games" className="panel p-5" />}>
        <GamesView searchParams={searchParams} />
      </Suspense>
    </>
  );
}
