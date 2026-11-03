import Link from "next/link";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { Panel } from "@/components/data/panel";
import { Unavailable } from "@/components/data/unavailable";
import { serverPostTry, serverTry } from "@/lib/api/server";
import type {
  GameSummary,
  Leaders,
  ModelReleaseSummary,
  PlayerGameLine,
  PlayerGameLinePage,
  MatchupHistory,
  PlayerProfile,
  TeamSeasonStats,
  UpcomingForecast,
} from "@/lib/api/types";
import { formatGameDate, formatGameTime, formatStat } from "@/lib/format";
import { param, type SearchParams } from "@/lib/url";

import { Forecast } from "./forecast";
import { GamePicker } from "./game-picker";
import { PlayerCard } from "./player-card";
import { PredictPicker } from "./predict-client";

const PLAYER_ID = /^\d{1,10}$/;
const LOOKAHEAD_DAYS = 14;
const FORM_GAMES = 5;
/** Recent games plotted behind the forecast range. */
const RANGE_GAMES = 20;

const DAY_MS = 86_400_000;
const daysBetween = (from: string, to: string) =>
  Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS);

function servingNote(releases: ModelReleaseSummary[] | null): { title: string; body: string } {
  const active = releases?.find((r) => r.status === "active");
  const latest = releases?.[0];
  if (active) {
    return {
      title: "Forecasts for upcoming games aren't published yet",
      body: `Release ${active.version} is active, but pre-game forecasts haven't been generated for this game.`,
    };
  }
  if (latest) {
    return {
      title: "No model is serving predictions yet",
      body: `The latest release, ${latest.version}, is a candidate still under evaluation. Forecasts appear here once a release is activated; each one is stored before tip-off and scored against the final box score.`,
    };
  }
  return {
    title: "No model has been trained yet",
    body: "Forecasts appear here once a model has been trained, tested on a season it never saw and switched on.",
  };
}

function average(lines: PlayerGameLine[], key: "pts" | "reb" | "ast" | "min"): number | null {
  if (!lines.length) return null;
  const total = lines.reduce((sum, l) => sum + (key === "min" ? l.minutes : l.box[key]), 0);
  return Math.round((total / lines.length) * 10) / 10;
}

async function QuickPicks() {
  const result = await serverTry<Leaders>("/leaders", { stat: "pts", limit: 8 });
  if (result.error || !result.data.leaders.length) return null;
  return (
    <div>
      <p className="kicker mb-2">Or start with a {result.data.season} scoring leader</p>
      <ul className="flex flex-wrap gap-2">
        {result.data.leaders.map((l) => (
          <li key={l.player_id}>
            <Link
              href={`/predict?player=${l.player_id}`}
              className="flex items-center gap-2 rounded-full border border-border bg-card py-1 pr-3 pl-1 text-subhead transition-colors duration-150 hover:bg-muted"
            >
              <PlayerAvatar id={l.player_id} name={l.full_name} team={l.team} size="sm" />
              {l.full_name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Who has actually guarded this player in past meetings. The real matchup is only known afterwards. */
function GuardedBy({ history, name }: { history: MatchupHistory | null; name: string }) {
  const defenders = history?.defenders ?? [];
  if (defenders.length === 0) return null;
  return (
    <div className="space-y-2 border-t border-border pt-4">
      <h4 className="kicker">Most often guarded by</h4>
      <p className="text-footnote text-muted-foreground">
        From past games against players now on this team. This is not a confirmed matchup: who guards{" "}
        {name} tonight is only known after the game.
      </p>
      <div role="region" aria-label="Most often guarded by" tabIndex={0} className="scroll-quiet overflow-x-auto">
        <table className="w-full text-subhead tabular-nums">
          <caption className="sr-only">
            Defenders now on this team, with the possessions they guarded {name} and the points {name} scored
          </caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="kicker py-1.5 text-left font-medium">
                Defender
              </th>
              <th scope="col" className="kicker py-1.5 text-right font-medium">
                Possessions
              </th>
              <th scope="col" className="kicker py-1.5 pl-3 text-right font-medium">
                Points per 100
              </th>
            </tr>
          </thead>
          <tbody>
            {defenders.map((d) => (
              <tr key={d.player_id} className="border-b border-border/50 last:border-0">
                <th scope="row" className="py-1.5 text-left font-normal">
                  <span className="flex items-center gap-2">
                    <PlayerAvatar id={d.player_id} name={d.full_name} size="sm" />
                    <Link href={`/players/${d.player_id}`} className="hover:text-primary">
                      {d.full_name}
                    </Link>
                  </span>
                </th>
                <td className="py-1.5 text-right">{Math.round(d.possessions)}</td>
                <td className="py-1.5 pl-3 text-right font-semibold">{formatStat(d.pts_per_100)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {history?.usual_pts_per_100 != null && (
        <p className="text-footnote text-muted-foreground">
          For comparison, {name} usually scores {formatStat(history.usual_pts_per_100)} per 100 possessions. A
          small number of possessions can swing this a lot.
        </p>
      )}
    </div>
  );
}

function HeadToHead({
  history,
  name,
  opponent,
}: {
  history: MatchupHistory | null;
  name: string;
  opponent: string;
}) {
  return (
    <section aria-labelledby="head-to-head" className="space-y-3">
      <h3 id="head-to-head" className="kicker">
        {name} against the {opponent}
      </h3>
      {!history || history.games === 0 ? (
        <p className="text-subhead text-muted-foreground">
          No previous games against them since 2018-19, when these records start.
        </p>
      ) : (
        <>
          <p className="text-subhead">
            In <strong>{history.games}</strong> {history.games === 1 ? "game" : "games"} since{" "}
            {history.first_season}, {name} averaged{" "}
            <strong>{formatStat(history.averages.pts ?? null)} points</strong>,{" "}
            {formatStat(history.averages.reb ?? null)} rebounds and {formatStat(history.averages.ast ?? null)}{" "}
            assists against them. {name}&apos;s team won {history.wins} and lost {history.losses}.
          </p>
          <div
            role="region"
            aria-label={`Recent games against the ${opponent}`}
            tabIndex={0}
            className="overflow-x-auto"
          >
            <table className="w-full text-subhead tabular-nums">
              <thead className="text-footnote text-muted-foreground">
                <tr className="border-b border-border">
                  <th scope="col" className="py-1.5 text-left font-medium">
                    Date
                  </th>
                  <th scope="col" className="py-1.5 text-left font-medium">
                    Result
                  </th>
                  <th scope="col" className="py-1.5 text-right font-medium">
                    PTS
                  </th>
                  <th scope="col" className="py-1.5 text-right font-medium">
                    REB
                  </th>
                  <th scope="col" className="py-1.5 text-right font-medium">
                    AST
                  </th>
                </tr>
              </thead>
              <tbody>
                {history.meetings.slice(0, 5).map((m) => (
                  <tr key={m.game_id} className="border-b border-border/50 last:border-0">
                    <th scope="row" className="py-1.5 text-left font-normal">
                      {formatGameDate(m.game_date, true)}
                    </th>
                    <td className="py-1.5">
                      {m.result === "W" ? "Won" : m.result === "L" ? "Lost" : "—"} {m.team_score}–
                      {m.opponent_score}
                    </td>
                    <td className="py-1.5 text-right font-semibold">{m.box.pts}</td>
                    <td className="py-1.5 text-right">{m.box.reb}</td>
                    <td className="py-1.5 text-right">{m.box.ast}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <GuardedBy history={history} name={name} />
    </section>
  );
}

export async function PredictView({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const query = await searchParams;
  const raw = param(query, "player");
  const id = raw && PLAYER_ID.test(raw) ? raw : undefined;
  const picker = (
    <Panel id="pick" kicker="Step 1" title="Pick a player" className="lg:col-span-12">
      <div className="space-y-5">
        <PredictPicker />
        {!id && <QuickPicks />}
      </div>
    </Panel>
  );
  if (!id) {
    return <div className="grid gap-10 lg:grid-cols-12 lg:gap-x-12">{picker}</div>;
  }

  const [profile, upcoming, releases, history] = await Promise.all([
    serverTry<PlayerProfile>(`/players/${id}`),
    serverTry<GameSummary[]>("/games/upcoming", { player_id: id, days: LOOKAHEAD_DAYS }),
    serverTry<ModelReleaseSummary[]>("/models"),
    serverTry<PlayerGameLinePage>(`/players/${id}/games`, { season_type: "regular", limit: RANGE_GAMES }),
  ]);
  if (profile.error && profile.error.status !== 404) return <ApiErrorView error={profile.error} />;
  if (!profile.data) {
    return (
      <div className="grid gap-10 lg:grid-cols-12 lg:gap-x-12">
        {picker}
        <Unavailable kind="empty" title={`No player has id ${id}`} className="lg:col-span-12">
          Search for a player by name above.
        </Unavailable>
      </div>
    );
  }

  const { player, current_season: season, last_games: lastGames } = profile.data;
  const games = upcoming.data ?? [];
  const requested = param(query, "game");
  const game = games.find((g) => g.id === requested) ?? games[0] ?? null;
  const teamId = player.team?.id;
  const isHome = game && game.home.team.id === teamId;
  const opponent = game ? (isHome ? game.away.team : game.home.team) : null;
  const opponentStats = opponent
    ? await serverTry<TeamSeasonStats>(`/teams/${opponent.id}/stats`, { season: game!.season })
    : null;
  const recent = lastGames.slice(0, FORM_GAMES);
  const lastPlayed = lastGames[0]?.game_date;
  const gap = game && lastPlayed ? daysBetween(lastPlayed, game.game_date) : 0;
  const restDays = gap > 0 ? gap - 1 : null;
  const note = servingNote(releases.data);
  const serving = releases.data?.some((r) => r.status === "active") ?? false;
  const [forecasts, matchup] = await Promise.all([
    serving && games.length
      ? serverPostTry<UpcomingForecast[]>("/predictions/upcoming", {
          player_id: player.id,
          days: LOOKAHEAD_DAYS,
        })
      : null,
    opponent ? serverTry<MatchupHistory>(`/players/${player.id}/matchups/${opponent.id}`) : null,
  ]);
  const byGame = new Map((forecasts?.data ?? []).map((f) => [f.game.id, f]));
  const selected = game ? byGame.get(game.id) : undefined;
  const firstName = player.full_name.split(" ")[0];

  return (
    <div className="grid gap-10 lg:grid-cols-12 lg:gap-x-12">
      {picker}
      <PlayerCard player={player} season={season} className="lg:col-span-12" />
      <div className="grid content-start gap-5 lg:col-span-4">
        <Panel id="games" kicker="Step 2" title="Upcoming games">
          {upcoming.error ? (
            <ApiErrorView error={upcoming.error} />
          ) : games.length === 0 ? (
            <Unavailable kind="no_games" title={`No games in the next ${LOOKAHEAD_DAYS} days`}>
              {player.team
                ? "The schedule shows no upcoming games for this player's team in that window."
                : "This player isn't on a current roster."}
            </Unavailable>
          ) : (
            <GamePicker
              games={games}
              playerId={player.id}
              teamId={teamId!}
              selectedId={game?.id ?? null}
              forecasts={Object.fromEntries(
                [...byGame].map(([id, f]) => [
                  id,
                  f.prediction ? f.prediction.values.slice(0, 3).map((v) => v.point) : null,
                ]),
              )}
            />
          )}
        </Panel>
      </div>

      <Panel
        id="forecast"
        kicker="Step 3"
        title={game && opponent ? `Forecast ${isHome ? "vs" : "@"} ${opponent.abbreviation}` : "Forecast"}
        className="lg:col-span-8"
      >
        {!game || !opponent ? (
          <Unavailable kind="no_games" title="Pick an upcoming game">
            A forecast is made for one scheduled game at a time.
          </Unavailable>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <TeamMark team={opponent} size="md" />
              <div>
                <p className="font-semibold">
                  {isHome ? "Home vs" : "Away at"} {opponent.city} {opponent.name}
                </p>
                <p className="text-footnote text-muted-foreground">
                  {game.tipoff_at ? formatGameTime(game.tipoff_at) : formatGameDate(game.game_date, true)}
                  {game.arena ? ` · ${game.arena}` : ""}
                </p>
              </div>
            </div>

            {serving ? (
              <Forecast
                key={game.id}
                initial={selected?.prediction ?? null}
                unavailable={selected?.unavailable ?? null}
                playerId={player.id}
                gameId={game.id}
                playerName={player.full_name}
                opponentName={opponent.name}
                history={history.data?.items ?? []}
                seasonAverages={season?.per_game ?? null}
              />
            ) : (
              <Unavailable
                kind="no_model"
                title={note.title}
                action={
                  <Link href="/models" className="text-subhead font-medium text-primary hover:underline">
                    See how the models are evaluated
                  </Link>
                }
              >
                {note.body}
              </Unavailable>
            )}

            <HeadToHead
              history={matchup?.data ?? null}
              name={firstName}
              opponent={`${opponent.city} ${opponent.name}`}
            />

            <section aria-labelledby="good-to-know" className="space-y-3">
              <h3 id="good-to-know" className="kicker">
                Good to know
              </h3>
              <ul className="stat-grid text-subhead sm:grid-cols-3">
                <li className="p-4">
                  <span className="block text-footnote text-muted-foreground">Recent form</span>
                  {recent.length ? (
                    <>
                      <strong className="numeral my-1 block text-title1">
                        {formatStat(average(recent, "pts"))} pts
                      </strong>
                      per game over the last {recent.length} {recent.length === 1 ? "game" : "games"}
                    </>
                  ) : (
                    "No games played yet"
                  )}
                </li>
                <li className="p-4">
                  <span className="block text-footnote text-muted-foreground">Rest</span>
                  <strong className="numeral my-1 block text-title1">
                    {restDays == null
                      ? "—"
                      : restDays === 0
                        ? "None"
                        : `${restDays} ${restDays === 1 ? "day" : "days"}`}
                  </strong>
                  {restDays === 0 ? "Second game in two nights" : "off before this game"}
                </li>
                <li className="p-4">
                  <span className="block text-footnote text-muted-foreground">{opponent.name} defense</span>
                  <strong className="numeral my-1 block text-title1">
                    {formatStat(opponentStats?.data?.defensive_rating ?? null)}
                  </strong>
                  points allowed per 100 possessions this season (higher is easier to score on)
                </li>
              </ul>
            </section>
          </div>
        )}
      </Panel>
    </div>
  );
}
