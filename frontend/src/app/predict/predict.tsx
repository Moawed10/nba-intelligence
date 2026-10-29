import Link from "next/link";

import { PlayerAvatar } from "@/components/brand/player-avatar";
import { TeamMark } from "@/components/brand/team-mark";
import { ApiErrorView } from "@/components/data/api-error";
import { Panel } from "@/components/data/panel";
import { StatTile } from "@/components/data/stat-tile";
import { Unavailable } from "@/components/data/unavailable";
import { serverTry } from "@/lib/api/server";
import type {
  GameSummary,
  Leaders,
  ModelReleaseSummary,
  PlayerGameLine,
  PlayerProfile,
  TeamSeasonStats,
} from "@/lib/api/types";
import { formatGameDate, formatGameTime, formatStat } from "@/lib/format";
import { hrefWith, param, type SearchParams } from "@/lib/url";
import { cn } from "@/lib/utils";

import { PredictPicker } from "./predict-client";

const PLAYER_ID = /^\d{1,10}$/;
const LOOKAHEAD_DAYS = 14;
const FORM_GAMES = 5;
const FORM_STATS = [
  { key: "pts", label: "Points" },
  { key: "reb", label: "Rebounds" },
  { key: "ast", label: "Assists" },
  { key: "min", label: "Minutes" },
] as const;

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
    body: "Forecasts appear here once a model has been trained, evaluated on a held-out season and activated.",
  };
}

function GameOption({
  game,
  teamId,
  href,
  selected,
}: {
  game: GameSummary;
  teamId: number;
  href: string;
  selected: boolean;
}) {
  const home = game.home.team.id === teamId;
  const opponent = home ? game.away.team : game.home.team;
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors",
        selected ? "border-primary/70 bg-primary/10" : "border-border hover:border-foreground/25",
      )}
    >
      <TeamMark team={opponent} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block font-medium">
          {home ? "vs" : "@"} {opponent.city} {opponent.name}
        </span>
        <span className="block text-footnote text-muted-foreground">
          {game.tipoff_at ? formatGameTime(game.tipoff_at) : formatGameDate(game.game_date, true)}
        </span>
      </span>
    </Link>
  );
}

function average(lines: PlayerGameLine[], key: (typeof FORM_STATS)[number]["key"]): number | null {
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
              className="flex items-center gap-2 rounded-full border border-border py-1 pr-3 pl-1 text-subhead transition-colors hover:border-foreground/25"
            >
              <PlayerAvatar name={l.full_name} team={l.team} size="sm" />
              {l.full_name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
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
    return <div className="grid gap-5 lg:grid-cols-12">{picker}</div>;
  }

  const [profile, upcoming, releases] = await Promise.all([
    serverTry<PlayerProfile>(`/players/${id}`),
    serverTry<GameSummary[]>("/games/upcoming", { player_id: id, days: LOOKAHEAD_DAYS }),
    serverTry<ModelReleaseSummary[]>("/models"),
  ]);
  if (profile.error && profile.error.status !== 404) return <ApiErrorView error={profile.error} />;
  if (!profile.data) {
    return (
      <div className="grid gap-5 lg:grid-cols-12">
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

  return (
    <div className="grid gap-5 lg:grid-cols-12">
      {picker}
      <section
        aria-labelledby="player-name"
        className="panel flex flex-wrap items-center gap-4 p-4 sm:p-5 lg:col-span-12"
      >
        <PlayerAvatar name={player.full_name} team={player.team} size="lg" />
        <div className="min-w-0 flex-1">
          <h2 id="player-name" className="text-title3 font-semibold">
            <Link href={`/players/${player.id}`} className="hover:text-primary">
              {player.full_name}
            </Link>
          </h2>
          <p className="text-footnote text-muted-foreground">
            {[
              player.team ? `${player.team.city} ${player.team.name}` : "Not on a current roster",
              player.position,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {season && (
          <dl className="flex gap-6 text-center">
            {(["pts", "reb", "ast"] as const).map((k) => (
              <div key={k}>
                <dt className="kicker">{k.toUpperCase()}</dt>
                <dd className="text-title2 font-semibold tabular-nums">{formatStat(season.per_game[k])}</dd>
              </div>
            ))}
            <div>
              <dt className="kicker">GP</dt>
              <dd className="text-title2 font-semibold tabular-nums">{season.games_played}</dd>
            </div>
          </dl>
        )}
      </section>

      <Panel id="games" kicker="Step 2" title="Upcoming games" className="lg:col-span-4">
        {upcoming.error ? (
          <ApiErrorView error={upcoming.error} />
        ) : games.length === 0 ? (
          <Unavailable kind="no_games" title={`No games in the next ${LOOKAHEAD_DAYS} days`}>
            {player.team
              ? "The schedule shows no upcoming games for this player's team in that window."
              : "This player isn't on a current roster."}
          </Unavailable>
        ) : (
          <ul className="space-y-2">
            {games.map((g) => (
              <li key={g.id}>
                <GameOption
                  game={g}
                  teamId={teamId!}
                  selected={g.id === game?.id}
                  href={hrefWith("/predict", {}, { player: player.id, game: g.id })}
                />
              </li>
            ))}
          </ul>
        )}
      </Panel>

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

            <div>
              <h3 className="kicker mb-3">What a forecast would draw on · from final box scores so far</h3>
              {recent.length ? (
                <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {FORM_STATS.map(({ key, label }) => {
                    const form = average(recent, key);
                    const base = season ? season.per_game[key] : null;
                    return (
                      <StatTile
                        key={key}
                        label={label}
                        value={form}
                        delta={
                          form != null && base != null && season!.games_played > recent.length
                            ? { value: Math.round((form - base) * 10) / 10, versus: "season" }
                            : null
                        }
                        footnote={`Last ${recent.length} games`}
                        className="bg-muted/50"
                      />
                    );
                  })}
                </dl>
              ) : (
                <Unavailable kind="no_games" title="No completed games yet" />
              )}
              <dl className="mt-3 grid gap-3 text-subhead sm:grid-cols-3">
                <div className="rounded-xl bg-muted/50 p-4">
                  <dt className="text-footnote text-muted-foreground">Rest before this game</dt>
                  <dd className="font-semibold">
                    {restDays == null
                      ? "—"
                      : restDays === 0
                        ? "Back-to-back"
                        : `${restDays} ${restDays === 1 ? "day" : "days"}`}
                  </dd>
                  {lastPlayed && (
                    <dd className="text-footnote text-muted-foreground">
                      Last played {formatGameDate(lastPlayed, true)}
                    </dd>
                  )}
                </div>
                <div className="rounded-xl bg-muted/50 p-4">
                  <dt className="text-footnote text-muted-foreground">
                    {opponent.abbreviation} defensive rating
                  </dt>
                  <dd className="font-semibold tabular-nums">
                    {formatStat(opponentStats?.data?.defensive_rating ?? null)}
                  </dd>
                  <dd className="text-footnote text-muted-foreground">
                    Points allowed per 100 possessions, {game.season}
                    {opponentStats?.data ? ` · ${opponentStats.data.games} games` : ""}
                  </dd>
                </div>
                <div className="rounded-xl bg-muted/50 p-4">
                  <dt className="text-footnote text-muted-foreground">{opponent.abbreviation} pace</dt>
                  <dd className="font-semibold tabular-nums">
                    {formatStat(opponentStats?.data?.pace ?? null)}
                  </dd>
                  <dd className="text-footnote text-muted-foreground">Possessions per 48 minutes</dd>
                </div>
              </dl>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
