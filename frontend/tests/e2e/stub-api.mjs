// Stub of the FastAPI read endpoints for end-to-end tests. Every record is synthetic (season
// 2099-00, teams "Alpha"/"Bravo"), shaped like backend/openapi.json, and never shown outside tests.
import { createServer } from "node:http";

const PORT = Number(process.env.STUB_API_PORT ?? 8799);
const META = {
  data_freshness: {
    dataset: "player_game_logs",
    status: "fresh",
    last_successful_sync: "2099-11-10T12:00:00Z",
    data_version: 1,
    is_stale: false,
  },
};

const TEAMS = [
  { id: 1, abbreviation: "AAA", city: "Alpha", name: "Ants", conference: "East", division: "Atlantic", primary_color: null, secondary_color: null },
  { id: 2, abbreviation: "BBB", city: "Bravo", name: "Bears", conference: "West", division: "Pacific", primary_color: null, secondary_color: null },
];
const ref = ({ id, abbreviation, city, name }) => ({ id, abbreviation, city, name });

const POSITIONS = ["G", "F", "C", "G-F", "F-C"];
const PLAYERS = [
  ...Array.from({ length: 30 }, (_, i) => ({
    id: 1000 + i,
    full_name: i === 0 ? "Zed Fixture" : `Test Player ${String(i).padStart(2, "0")}`,
    position: POSITIONS[i % POSITIONS.length],
    is_active: true,
    team: ref(TEAMS[i % 2]),
    from_year: 2090,
    to_year: 2099,
  })),
  { id: 1990, full_name: "Former Fixture", position: "G", is_active: false, team: null, from_year: 2080, to_year: 2089 },
];

const SEASONS = ["2099-00", "2098-99"];
const GAMES_PER_SEASON = { "2099-00": 30, "2098-99": 2 };
const COUNTING = ["pts", "reb", "ast", "fg3m", "fg3a", "fgm", "fga", "ftm", "fta", "oreb", "dreb", "stl", "blk", "tov", "pf"];
const UNAVAILABLE_PLAYER = 9503;

const pct = (made, attempted) => (attempted ? Math.round((made / attempted) * 10000) / 10000 : null);
const round2 = (value) => Math.round(value * 100) / 100;

function box(n) {
  const fgm = 6 + (n % 5);
  const fg3m = n % 3;
  const dreb = 4 + (n % 4);
  return {
    fgm, fga: fgm + 6, fg3m, fg3a: fg3m + 2, ftm: 2, fta: 3, oreb: 1, dreb, reb: 1 + dreb,
    ast: 3 + (n % 6), stl: n % 2, blk: n % 3 === 0 ? 1 : 0, tov: 2, pf: 2,
    pts: 2 * fgm + fg3m + 2, plus_minus: (n % 7) - 3,
  };
}

function shooting(b) {
  return {
    fg_pct: pct(b.fgm, b.fga), fg_pct_status: null,
    fg3_pct: pct(b.fg3m, b.fg3a), fg3_pct_status: null,
    ft_pct: pct(b.ftm, b.fta), ft_pct_status: null,
  };
}

function gameLines(player, season) {
  const year = Number(season.slice(0, 4));
  const opponent = TEAMS[(player.team?.id ?? 1) % 2];
  return Array.from({ length: GAMES_PER_SEASON[season] ?? 0 }, (_, n) => {
    const b = box(n);
    return {
      game_id: `${String(year % 100).padStart(2, "0")}${String(n).padStart(8, "0")}`,
      game_date: new Date(Date.UTC(year, 9, 20 + n * 2)).toISOString().slice(0, 10),
      season,
      season_type: "regular",
      team_abbreviation: player.team?.abbreviation ?? "AAA",
      opponent: ref(opponent),
      is_home: n % 2 === 0,
      result: n % 3 ? "W" : "L",
      team_score: 110 + n,
      opponent_score: n % 3 ? 100 : 120,
      minutes: 30 + (n % 5),
      box: b,
      shooting: shooting(b),
      double_double: b.pts >= 10 && b.reb >= 10,
    };
  }).reverse();
}

function summary(lines) {
  const n = lines.length;
  const total = (k) => lines.reduce((t, l) => t + (k === "min" ? l.minutes : l.box[k]), 0);
  const totals = Object.fromEntries(COUNTING.map((k) => [k, total(k)]));
  totals.min = total("min");
  return {
    games_played: n,
    per_game: Object.fromEntries(
      ["pts", "reb", "ast", "fg3m", "stl", "blk", "tov", "min"].map((k) => [k, n ? round2(totals[k] / n) : null]),
    ),
    totals,
    shooting: {
      fg_pct: pct(totals.fgm, totals.fga), fg_pct_status: null,
      fg3_pct: pct(totals.fg3m, totals.fg3a), fg3_pct_status: null,
      ft_pct: pct(totals.ftm, totals.fta), ft_pct_status: null,
    },
    efg_pct: 0.55,
    ts_pct: 0.6,
    double_doubles: 0,
    pts_consistency: 0.2,
  };
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

function error(res, status, code, message) {
  send(res, status, { error: { code, message, request_id: "stub", details: [] } });
}

function playerRoute(res, id, resource, q, page) {
  if (id === UNAVAILABLE_PLAYER) return error(res, 503, "database_unavailable", "The database is temporarily unavailable.");
  const player = PLAYERS.find((p) => p.id === id);
  if (!player) return error(res, 404, "player_not_found", `No player with id ${id}.`);
  const seasons = player.is_active ? SEASONS : [];
  const season = seasons.includes(q.get("season")) ? q.get("season") : seasons[0];
  const lines = season ? gameLines(player, season) : [];

  if (!resource) {
    return send(res, 200, {
      player: { ...player, first_name: null, last_name: null, height_inches: 79, weight_lbs: 215, birthdate: null },
      current_season: season ? { ...summary(lines), season, season_type: "regular" } : null,
      last_games: lines.slice(0, 5),
      meta: META,
    });
  }
  if (resource === "stats") {
    return send(res, 200, {
      player_id: id,
      season_type: "regular",
      seasons: seasons.map((s) => ({ ...summary(gameLines(player, s)), season: s, season_type: "regular" })),
      splits_season: season ?? null,
      splits: season
        ? [
            { key: "home", label: "Home", summary: summary(lines.filter((l) => l.is_home)) },
            { key: "away", label: "Away", summary: summary(lines.filter((l) => !l.is_home)) },
          ]
        : [],
      meta: META,
    });
  }
  if (resource === "trends") {
    const stat = q.get("stat") ?? "pts";
    const ordered = [...lines].reverse();
    const values = ordered.map((l) => (stat === "min" ? l.minutes : l.box[stat]));
    const rolling = (n, i) => (i >= n ? round2(values.slice(i - n, i).reduce((a, b) => a + b, 0) / n) : null);
    return send(res, 200, {
      player_id: id,
      stat,
      season,
      season_type: null,
      games_played: values.length,
      average: values.length ? round2(values.reduce((a, b) => a + b, 0) / values.length) : null,
      points: ordered.map((l, i) => ({
        game_id: l.game_id,
        game_date: l.game_date,
        opponent_abbreviation: l.opponent.abbreviation,
        is_home: l.is_home,
        value: values[i],
        rolling_3: rolling(3, i),
        rolling_5: rolling(5, i),
        rolling_10: rolling(10, i),
      })),
      meta: META,
    });
  }
  return send(res, 200, page(lines));
}

createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const q = url.searchParams;
  const path = url.pathname.replace(/^\/api\/v1/, "");
  const limit = Number(q.get("limit") ?? 25);
  const offset = Number(q.get("offset") ?? 0);
  const page = (items) => ({ items: items.slice(offset, offset + limit), total: items.length, limit, offset, meta: META });

  if (path === "/health") return send(res, 200, { status: "ok" });
  if (path === "/teams") return send(res, 200, TEAMS);
  if (path === "/players") {
    let items = PLAYERS;
    if (q.get("team_id")) items = items.filter((p) => String(p.team?.id) === q.get("team_id"));
    if (q.get("position")) items = items.filter((p) => p.position?.includes(q.get("position")));
    if (q.get("active") === "true") items = items.filter((p) => p.is_active);
    return send(res, 200, page([...items].sort((a, b) => a.full_name.localeCompare(b.full_name))));
  }
  if (path === "/players/search") {
    const term = (q.get("q") ?? "").toLowerCase();
    const results = PLAYERS.filter((p) => p.full_name.toLowerCase().includes(term))
      .slice(0, Number(q.get("limit") ?? 10))
      .map((p) => ({
        id: p.id,
        full_name: p.full_name,
        position: p.position,
        is_active: p.is_active,
        team_abbreviation: p.team?.abbreviation ?? null,
      }));
    return send(res, 200, results);
  }
  const match = path.match(/^\/players\/(\d+)(?:\/(stats|trends|games))?$/);
  if (match) return playerRoute(res, Number(match[1]), match[2], q, page);
  return error(res, 404, "not_found", "Resource not found.");
}).listen(PORT, "127.0.0.1", () => console.log(`stub API listening on ${PORT}`));
