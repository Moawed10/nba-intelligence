import Link from "next/link";

import type { HomeCourt, VenueSplit } from "@/lib/api/types";
import { formatCount, formatStat } from "@/lib/format";

const FEW_GAMES = 5;

function Venue({ label, split }: { label: string; split: VenueSplit }) {
  return (
    <div className="px-4 py-3.5">
      <dt className="kicker">{label}</dt>
      <dd className="numeral mt-1.5 text-[2.5rem]">
        {split.wins}–{split.losses}
      </dd>
      <dd className="mt-1 text-footnote text-muted-foreground tabular-nums">
        {formatStat(split.pts_per_game)} scored · {formatStat(split.opp_pts_per_game)} allowed
      </dd>
    </div>
  );
}

const signed = (value: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatStat(Math.abs(value))}`;

/** Results at home and away: what the numbers show, without claiming why. */
export function HomeCourtSection({ data, teamName }: { data: HomeCourt; teamName: string }) {
  const compared = data.players
    .flatMap((p) => {
      const home = p.home.pts;
      const away = p.away.pts;
      return home == null || away == null ? [] : [{ ...p, gap: home - away, homePts: home, awayPts: away }];
    })
    .sort((a, b) => b.gap - a.gap);
  const small = data.home.games < FEW_GAMES || data.away.games < FEW_GAMES;
  return (
    <div className="space-y-6">
      <dl className="stat-grid grid-cols-1 sm:grid-cols-3">
        <Venue label="At home" split={data.home} />
        <Venue label="On the road" split={data.away} />
        <div className="px-4 py-3.5">
          <dt className="kicker">Home crowd</dt>
          <dd className="numeral mt-1.5 text-[2.5rem]">{formatCount(data.average_attendance)}</dd>
          <dd className="mt-1 text-footnote text-muted-foreground tabular-nums">
            {data.attendance_games
              ? `Average over ${data.attendance_games} reported ${data.attendance_games === 1 ? "game" : "games"}`
              : "Not reported yet"}
          </dd>
        </div>
      </dl>
      {compared.length > 0 && (
        <div
          role="region"
          aria-label="Scoring at home and away"
          tabIndex={0}
          className="scroll-quiet overflow-x-auto"
        >
          <table className="w-full text-subhead tabular-nums">
            <caption className="sr-only">
              {teamName} players&apos; points per game at home and on the road, biggest home gain first
            </caption>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="kicker py-2 pr-3 text-left">
                  Player
                </th>
                <th scope="col" className="kicker px-3 py-2 text-right">
                  Home PTS
                </th>
                <th scope="col" className="kicker px-3 py-2 text-right">
                  Away PTS
                </th>
                <th scope="col" className="kicker px-3 py-2 text-right">
                  Difference
                </th>
                <th scope="col" className="kicker py-2 pl-3 text-right">
                  Games
                </th>
              </tr>
            </thead>
            <tbody>
              {compared.map((p) => (
                <tr key={p.player_id} className="border-b border-border/60">
                  <th scope="row" className="py-2 pr-3 text-left font-normal whitespace-nowrap">
                    <Link href={`/players/${p.player_id}`} className="hover:text-primary">
                      {p.full_name}
                    </Link>
                  </th>
                  <td className="px-3 py-2 text-right">{formatStat(p.homePts)}</td>
                  <td className="px-3 py-2 text-right">{formatStat(p.awayPts)}</td>
                  <td className="px-3 py-2 text-right font-semibold">{signed(p.gap)}</td>
                  <td className="py-2 pl-3 text-right text-muted-foreground">
                    {p.home_games} / {p.away_games}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="max-w-3xl text-footnote text-muted-foreground">
        {data.season} regular season. These are real results, and they show a difference, not its cause:
        schedule and opponents play a part too.
        {small && " It's early in the season, so a few games can swing these numbers a lot."}
      </p>
    </div>
  );
}
