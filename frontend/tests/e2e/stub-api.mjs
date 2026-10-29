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
  { id: 1, abbreviation: "AAA", city: "Alpha", name: "Ants", conference: "East", division: "Atlantic", primary_color: "#1D428A", secondary_color: "#FFC72C" },
  { id: 2, abbreviation: "BBB", city: "Bravo", name: "Bears", conference: "West", division: "Pacific", primary_color: "#CE1141", secondary_color: "#000000" },
];
const ref = ({ id, abbreviation, city, name, primary_color, secondary_color }) => ({
  id, abbreviation, city, name, primary_color, secondary_color,
});

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
    const b = box(n + (player.id % 5));
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

// Team history: Bravo were the "Old Town Owls" in 2070-71, before turnovers and ratings were recorded.
const historic = (team, season, city, name, wins, early) => ({
  season, city, name, games: 82, wins, losses: 82 - wins, win_pct: Math.round((wins / 82) * 10000) / 10000,
  conference_rank: 1, division_rank: 1, playoff_wins: early ? 0 : 16, playoff_losses: early ? 0 : 4,
  finals: early ? null : "champion",
  per_game: { pts: 110 + team, reb: 44, oreb: early ? null : 10, ast: 25, stl: early ? null : 8, blk: early ? null : 5,
    tov: early ? null : 14, fg3m: early ? null : 12, pf: 20 },
  fg_pct: 0.47, fg3_pct: early ? null : 0.36, ft_pct: 0.77,
  pace: early ? null : 99, off_rating: early ? null : 112 + team, def_rating: early ? null : 106, net_rating: early ? null : 6 + team,
});
const HISTORY = {
  1: [historic(1, "2099-00", "Alpha", "Ants", 60, false), historic(1, "2098-99", "Alpha", "Ants", 50, false)],
  2: [historic(2, "2099-00", "Bravo", "Bears", 30, false), historic(2, "2070-71", "Old Town", "Owls", 41, true)],
};

const TODAY = "2099-11-10";
const game = (id, date, away, home, status, scores) => ({
  id, season: "2099-00", season_type: "regular", game_date: date, status,
  tipoff_at: `${date}T23:30:00Z`, arena: "Fixture Arena",
  away: { team: ref(TEAMS[away]), score: scores?.[0] ?? null },
  home: { team: ref(TEAMS[home]), score: scores?.[1] ?? null },
});
const GAMES = [
  game("0099000101", "2099-11-09", 0, 1, "final", [101, 112]),
  game("0099000102", TODAY, 1, 0, "scheduled"),
  game("0099000103", "2099-11-12", 0, 1, "scheduled"),
];

function teamStats(id) {
  const t = TEAMS.find((x) => x.id === id);
  return {
    team_id: id, season: "2099-00", season_type: "regular", games: 10,
    record: id === 1 ? { wins: 6, losses: 4 } : { wins: 3, losses: 7 },
    pts_per_game: 110, opp_pts_per_game: 108, possessions_per_game: 100,
    offensive_rating: id === 1 ? 114.2 : 108.5, defensive_rating: id === 1 ? 109.1 : 111.9,
    net_rating: id === 1 ? 5.1 : -3.4, pace: id === 1 ? 99.5 : 101.2,
    shooting: shooting(box(t.id)), meta: META,
  };
}

function boxScore(g) {
  const teams = [g.away, g.home].map((side, i) => {
    const players = PLAYERS.filter((p) => p.is_active && p.team.id === side.team.id).slice(0, 5)
      .map((p, n) => {
        const b = box(n + i);
        return { player_id: p.id, full_name: p.full_name, minutes: 30, box: b, shooting: shooting(b), double_double: false };
      });
    return { team: side.team, is_home: i === 1, minutes: 240, players, totals: box(i), shooting: shooting(box(i)) };
  });
  return { game: g, stats_finalized: true, teams, meta: META };
}

function leaders(stat, limit) {
  const rows = PLAYERS.filter((p) => p.is_active)
    .map((p) => ({ p, s: summary(gameLines(p, "2099-00")) }))
    .map(({ p, s }) => ({ player_id: p.id, full_name: p.full_name, team: p.team, games_played: s.games_played, value: s.per_game[stat] ?? 0 }))
    .sort((a, b) => b.value - a.value || a.full_name.localeCompare(b.full_name))
    .slice(0, limit)
    .map((row, i) => ({ ...row, rank: i + 1 }));
  return { season: "2099-00", stat, minimum_games: 21, qualified_players: 30, leaders: rows, meta: META };
}

const STANDOUTS = {
  window_start: "2099-11-03", window_end: "2099-11-09",
  criterion: "Highest Game Score in completed games over the 7 days ending on the latest final",
  performances: PLAYERS.slice(0, 3).map((p, i) => {
    const b = box(10 - i);
    return {
      game_id: "0099000101", game_date: "2099-11-09", player_id: p.id, full_name: p.full_name,
      team: p.team, opponent: ref(TEAMS[p.team.id % 2]), is_home: p.team.id === 2,
      result: p.team.id === 2 ? "W" : "L", minutes: 34, box: b, shooting: shooting(b),
      game_score: 30 - i * 2.5, double_double: false,
    };
  }),
  meta: META,
};

const RELEASE = {
  version: "2099.11.10-1", status: "active", created_at: "2099-11-10T12:00:00Z", activated_at: "2099-11-10T12:30:00Z",
  data_version: 1, feature_schema_version: "stub", git_sha: "0000000",
  train_start: "2090-10-01", train_end: "2095-06-30", val_start: "2095-10-01", val_end: "2096-06-30",
  test_start: "2096-10-01", test_end: "2097-06-30",
  selected: { pts: "xgboost", reb: "ridge", double_double: "logistic" },
};
const METRICS = [
  { target: "pts", algorithm: "xgboost", n: 1000, mae: 4.5, rmse: 6.0, r2: 0.5, baseline_mae: 4.7, interval_coverage: 0.8, brier: null, log_loss: null },
  { target: "reb", algorithm: "ridge", n: 1000, mae: 1.9, rmse: 2.5, r2: 0.45, baseline_mae: 1.95, interval_coverage: 0.81, brier: null, log_loss: null },
  { target: "double_double", algorithm: "logistic", n: 1000, mae: null, rmse: null, r2: null, baseline_mae: null, interval_coverage: null, brier: 0.05, log_loss: 0.18 },
];
const SNAPSHOT = { release: RELEASE, test_season: "2096-97", metrics: METRICS };
const DATASETS = ["schedule", "final_box_scores", "player_game_logs"].map((dataset) => ({
  dataset, status: "fresh", last_successful_sync: "2099-11-10T12:00:00Z", last_attempted_sync: "2099-11-10T12:00:00Z",
  last_error: null, coverage_start: "2098-10-20", coverage_end: "2099-11-09",
}));

createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const q = url.searchParams;
  const path = url.pathname.replace(/^\/api\/v1/, "");
  const limit = Number(q.get("limit") ?? 25);
  const offset = Number(q.get("offset") ?? 0);
  const page = (items) => ({ items: items.slice(offset, offset + limit), total: items.length, limit, offset, meta: META });

  if (path === "/health") return send(res, 200, { status: "ok" });
  if (path === "/teams") return send(res, 200, TEAMS);
  if (path === "/data-status") {
    return send(res, 200, {
      generated_at: "2099-11-10T12:00:00Z",
      data_version: 1,
      datasets: [],
      seasons: SEASONS.map((season) => ({ season, final_games: GAMES_PER_SEASON[season], remaining_games: 0, player_lines: 0 })),
      row_counts: {},
    });
  }
  if (path === "/overview") {
    return send(res, 200, {
      generated_at: "2099-11-10T12:00:00Z", today: TODAY,
      upcoming: GAMES.filter((g) => g.status === "scheduled"),
      recent: GAMES.filter((g) => g.status === "final"),
      leaders: leaders("pts", 5), standouts: STANDOUTS, model: SNAPSHOT, datasets: DATASETS,
    });
  }
  if (path === "/leaders") return send(res, 200, leaders(q.get("stat") ?? "pts", Number(q.get("limit") ?? 10)));
  if (path === "/standouts") return send(res, 200, STANDOUTS);
  if (path === "/games/upcoming") {
    const player = PLAYERS.find((p) => String(p.id) === q.get("player_id"));
    const plays = (g) => !q.get("player_id") || [g.home.team.id, g.away.team.id].includes(player?.team?.id);
    return send(res, 200, GAMES.filter((g) => g.status === "scheduled" && plays(g)));
  }
  if (path === "/games") {
    const from = q.get("date_from") ?? "0000", to = q.get("date_to") ?? "9999";
    return send(res, 200, page(GAMES.filter((g) => g.game_date >= from && g.game_date <= to)));
  }
  const boxMatch = path.match(/^\/games\/(\w+)\/boxscore$/);
  if (boxMatch) {
    const g = GAMES.find((x) => x.id === boxMatch[1]);
    return g ? send(res, 200, boxScore(g)) : error(res, 404, "game_not_found", "No such game.");
  }
  const historyMatch = path.match(/^\/teams\/(\d+)\/history$/);
  if (historyMatch) {
    const team = TEAMS.find((t) => t.id === Number(historyMatch[1]));
    if (!team) return error(res, 404, "team_not_found", "No team with that id.");
    return send(res, 200, { team: ref(team), seasons: HISTORY[team.id], meta: META });
  }
  const statsMatch = path.match(/^\/teams\/(\d+)\/stats$/);
  if (statsMatch) return send(res, 200, teamStats(Number(statsMatch[1])));
  if (path === "/models") return send(res, 200, [{ ...RELEASE }]);
  if (path === `/models/${RELEASE.version}`) {
    return send(res, 200, {
      ...RELEASE, test_season: "2096-97", selected_metrics: METRICS,
      algorithms: [
        { target: "pts", algorithm: "rolling_baseline", selected: false, validation_mae: 4.8, test_mae: 4.7, test_rmse: 6.2, test_r2: 0.44 },
        { target: "pts", algorithm: "ridge", selected: false, validation_mae: 4.6, test_mae: 4.6, test_rmse: 6.1, test_r2: 0.47 },
        { target: "pts", algorithm: "xgboost", selected: true, validation_mae: 4.5, test_mae: 4.5, test_rmse: 6.0, test_r2: 0.5 },
      ],
      features: ["pts_avg_10", "min_avg_10", "rest_days"],
      interval_calibration: Object.fromEntries(["pts", "reb"].map((t, i) => [t, {
        alpha: 0.2, method: "mondrian_split_conformal", binned_by: "predicted_minutes",
        edges: [18, 27], counts: [300, 300, 300], quantiles: [3 + i, 5 + i, 7 + i],
      }])),
    });
  }
  if (path.startsWith("/models/")) return error(res, 404, "model_not_found", "No such model version.");
  // Predictions are stateless here: GET lists none, POST returns a fixed synthetic forecast.
  if (path === "/predictions" && req.method === "GET") return send(res, 200, []);
  if (path === "/predictions" && req.method === "POST") {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      const { player_id, game_id } = JSON.parse(raw || "{}");
      if (player_id === 1001) {
        return error(res, 422, "insufficient_data", "Forecasts need at least 5 games this season or last; this player has 2.");
      }
      const value = (stat, point, half) => ({ stat, point, lower: Math.max(0, point - half), upper: point + half, interval_level: 0.8 });
      send(res, 201, {
        id: "00000000-0000-4000-8000-000000000001", player_id, game_id, release_version: RELEASE.version,
        kind: "pregame", status: "ok", created_at: "2099-11-10T12:00:00Z", data_cutoff_at: "2099-11-10T12:00:00Z",
        feature_schema_version: "stub", double_double_probability: 0.25, supersedes_prediction_id: null,
        values: [value("pts", 24, 8), value("reb", 7, 3), value("ast", 5, 2.5), value("fg3m", 2, 1.5),
          value("stl", 1, 1), value("blk", 0.5, 0.5), value("min", 33, 6)],
        explanation: { method: "inputs", inputs: { pts: { pts_avg_5: 23, pts_avg_10: 22, pts_season_avg: 21, pts_vs_opponent: 20 } }, context: {} },
      });
    });
    return;
  }
  if (path === "/players") {
    let items = PLAYERS;
    const season = q.get("season");
    if (season) {
      items = items
        .filter((p) => p.is_active && GAMES_PER_SEASON[season])
        .map((p) => {
          const s = summary(gameLines(p, season));
          return {
            ...p,
            season_averages: {
              season, games_played: s.games_played, ...s.per_game,
              fg_pct: s.shooting.fg_pct, fg_pct_status: null,
            },
          };
        });
    }
    if (q.get("team_id")) items = items.filter((p) => String(p.team?.id) === q.get("team_id"));
    if (q.get("position")) items = items.filter((p) => p.position?.includes(q.get("position")));
    if (q.get("active") === "true") items = items.filter((p) => p.is_active);
    const sort = q.get("sort") ?? "full_name";
    const key = sort.replace(/^-/, "");
    const value = (p) => (key === "full_name" ? p.full_name : key === "games" ? p.season_averages.games_played : p.season_averages[key]);
    const sorted = [...items].sort((a, b) => {
      const order = key === "full_name" ? a.full_name.localeCompare(b.full_name) : value(a) - value(b);
      return (sort.startsWith("-") ? -order : order) || a.full_name.localeCompare(b.full_name);
    });
    return send(res, 200, page(sorted));
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
