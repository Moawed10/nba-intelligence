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
  id, season: "2099-00", season_type: "regular", game_date: date, status, live_status: null,
  tipoff_at: `${date}T23:30:00Z`, arena: "Fixture Arena",
  away: { team: ref(TEAMS[away]), score: scores?.[0] ?? null },
  home: { team: ref(TEAMS[home]), score: scores?.[1] ?? null },
});
const GAMES = [
  { ...game("0099000100", "2099-11-07", 1, 0, "in_progress", [58, 61]), live_status: "Q3 5:12", tipoff_at: new Date(Date.now() - 3_600_000).toISOString() },
  { ...game("0099000099", "2099-11-06", 1, 0, "in_progress", [40, 50]), live_status: "Q2 1:00", tipoff_at: new Date(Date.now() - 3_600_000).toISOString() },
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

function leaders(stat, limit, teamId) {
  const rows = PLAYERS.filter((p) => p.is_active && (!teamId || p.team?.id === teamId))
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
  if (path === "/overview" || path === "/games/0099000099") {
    GAMES.find((g) => g.id === "0099000099").home.score += 1;
  }
  if (path === "/overview") {
    return send(res, 200, {
      generated_at: "2099-11-10T12:00:00Z", today: TODAY,
      live: GAMES.filter((g) => g.status === "in_progress"),
      upcoming: GAMES.filter((g) => g.status === "scheduled"),
      recent: GAMES.filter((g) => g.status === "final"),
      leaders: leaders("pts", 5), standouts: STANDOUTS, model: SNAPSHOT, datasets: DATASETS,
    });
  }
  if (path === "/leaders") {
    return send(res, 200, leaders(q.get("stat") ?? "pts", Number(q.get("limit") ?? 10), Number(q.get("team_id")) || null));
  }
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
  const detailMatch = path.match(/^\/games\/(\d{10})$/);
  if (detailMatch) {
    // Game-log rows link to their game; those fixture games exist only as a final score.
    const g =
      GAMES.find((x) => x.id === detailMatch[1]) ??
      (detailMatch[1].startsWith("99") ? game(detailMatch[1], "2099-10-15", 0, 1, "final", [100, 105]) : null);
    if (!g) return error(res, 404, "game_not_found", "No such game.");
    return send(res, 200, { ...g, status_observed_at: null, stats_finalized: g.status === "final", meta: META });
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
  if (path === `/models/${RELEASE.version}/live`) {
    return send(res, 200, {
      version: RELEASE.version, status: RELEASE.status, activated_at: RELEASE.activated_at, games: 2,
      stats: [{ stat: "pts", n: 6, mae: 5.25, interval_coverage: 0.8333 }, { stat: "reb", n: 6, mae: 2.1, interval_coverage: 0.6667 }],
      double_double: { n: 6, brier: 0.07 },
      game_scores: { games: 2, points_mae: 7.25, interval_coverage: 0.75, brier: 0.18, winner_accuracy: 0.5 },
    });
  }
  if (path === `/models/${RELEASE.version}/analytics`) {
    const stat = q.get("stat") ?? "pts";
    const kind = q.get("kind") ?? "backtest";
    if (kind === "pregame") {
      return send(res, 200, { version: RELEASE.version, kind, stat, algorithm: "xgboost", n: 0, first_game: null,
        last_game: null, mae: null, rmse: null, bias: null, interval_level: 0.8, coverage: null,
        calibration: [], residuals: [], coverage_by_bin: [] });
    }
    const scale = stat === "pts" ? 1 : 0.4;
    return send(res, 200, {
      version: RELEASE.version, kind, stat, algorithm: "xgboost", n: 1000, first_game: "2096-10-22",
      last_game: "2097-04-14", mae: 4.5 * scale, rmse: 5.9 * scale, bias: -0.1, interval_level: 0.8, coverage: 0.8,
      calibration: Array.from({ length: 10 }, (_, i) => ({ predicted: (3 + i * 2.5) * scale, actual: (3.2 + i * 2.5) * scale, n: 100 })),
      residuals: [{ lower: -6, upper: -2, n: 150 }, { lower: -2, upper: 2, n: 700 }, { lower: 2, upper: 6, n: 150 }],
      coverage_by_bin: [
        { minutes_from: null, minutes_to: 18.5, n: 300, coverage: 0.79 },
        { minutes_from: 18.5, minutes_to: 28.3, n: 400, coverage: 0.8 },
        { minutes_from: 28.3, minutes_to: null, n: 300, coverage: 0.81 },
      ],
    });
  }
  if (path.startsWith("/models/")) return error(res, 404, "model_not_found", "No such model version.");
  // Predictions are stateless here: GET lists none, POST returns a fixed synthetic forecast whose
  // points depend on the game, so switching games visibly changes the numbers.
  const stubForecast = (player_id, game_id) => {
    const pts = game_id === "0099000103" ? 26 : 24;
    const value = (stat, point, half) => ({ stat, point, lower: Math.max(0, point - half), upper: point + half, interval_level: 0.8 });
    return {
      id: `00000000-0000-4000-8000-0000000000${game_id.slice(-2)}`, player_id, game_id, release_version: RELEASE.version,
      kind: "pregame", status: "ok", created_at: "2099-11-10T12:00:00Z", data_cutoff_at: "2099-11-10T12:00:00Z",
      feature_schema_version: "stub", double_double_probability: 0.25, supersedes_prediction_id: null,
      freshness: "current", freshness_reason: null, actuals: null,
      values: [value("pts", pts, 8), value("reb", 7, 3), value("ast", 5, 2.5), value("fg3m", 2, 1.5),
        value("stl", 1, 1), value("blk", 0.5, 0.5), value("min", 33, 6)],
      explanation: { method: "inputs", inputs: { pts: { pts_avg_5: 23, pts_avg_10: 22, pts_season_avg: 21, pts_vs_opponent: 20 } }, context: {} },
    };
  };
  const tooFew = { code: "insufficient_data", message: "Forecasts need at least 5 games this season or last; this player has 2." };
  const reviewMatch = path.match(/^\/predictions\/games\/(\d{10})$/);
  if (reviewMatch) {
    const g = GAMES.find((x) => x.id === reviewMatch[1]);
    if (!g) return error(res, 404, "game_not_found", "No such game.");
    const final = g.status === "final";
    const side = (team, points) => ({ team_id: team.id, points, lower: points - 15, upper: points + 15 });
    const forecast = g.id === "0099000101" ? {
      id: "00000000-0000-4000-8000-0000000000bb", game_id: g.id, release_version: "2099.11.01-1",
      home: side(g.home.team, 108.2), away: side(g.away.team, 104.6), home_win_probability: 0.62,
      interval_level: 0.8, created_at: "2099-11-09T12:00:00Z", data_cutoff_at: "2099-11-09T12:00:00Z",
      supersedes_prediction_id: null,
    } : null;
    return send(res, 200, {
      game_id: g.id, status: g.status, forecast, evaluation: null,
      home_score: final ? g.home.score : null, away_score: final ? g.away.score : null,
      picked_winner: forecast && final ? (forecast.home_win_probability >= 0.5) === (g.home.score > g.away.score) : null,
    });
  }
  if (path === "/predictions/games" && req.method === "POST") {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      const { game_ids = [] } = JSON.parse(raw || "{}");
      send(res, 200, game_ids.map((id) => {
        const g = GAMES.find((x) => x.id === id);
        if (!g || g.id === "0099000103") {
          return { game_id: id, forecast: null, unavailable: { code: "insufficient_data", message: "Score forecasts need 10 earlier games for each team; one team has 4." } };
        }
        const side = (team, points) => ({ team_id: team.id, points, lower: points - 15, upper: points + 15 });
        return {
          game_id: id, unavailable: null,
          forecast: {
            id: "00000000-0000-4000-8000-0000000000aa", game_id: id, release_version: "2099.11.01-1",
            home: side(g.home.team, 114.6), away: side(g.away.team, 108.2), home_win_probability: 0.68,
            interval_level: 0.8, created_at: "2099-11-10T12:00:00Z", data_cutoff_at: "2099-11-10T12:00:00Z",
            supersedes_prediction_id: null, freshness: "current", freshness_reason: null,
          },
        };
      }));
    });
    return;
  }
  if (path === "/predictions/history") {
    const player = PLAYERS.find((p) => p.id === Number(q.get("player_id")));
    if (!player) return error(res, 404, "player_not_found", "No such player.");
    const kind = q.get("kind") ?? "backtest";
    const value = (point, actual) => ({ point, lower: point - 8, upper: point + 8, actual, within_interval: Math.abs(actual - point) <= 8 });
    const entries = kind === "pregame" ? [] : [
      { prediction_id: "b1", kind, release_version: RELEASE.version, game_id: "0099600002", game_date: "2097-04-14",
        opponent: ref(TEAMS[1]), is_home: true, values: { pts: value(24, 30), reb: value(7, 5), ast: value(5, 6) } },
      { prediction_id: "b2", kind, release_version: RELEASE.version, game_id: "0099600001", game_date: "2097-04-12",
        opponent: ref(TEAMS[1]), is_home: false, values: { pts: value(22, 35), reb: value(6, 6), ast: value(4, 3) } },
    ];
    return send(res, 200, { player_id: player.id, kind, entries });
  }
  if (path === "/predictions" && req.method === "GET") return send(res, 200, []);
  if ((path === "/predictions" || path === "/predictions/upcoming") && req.method === "POST") {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      const { player_id, game_id } = JSON.parse(raw || "{}");
      if (path === "/predictions") {
        if (player_id === 1001) return error(res, 422, tooFew.code, tooFew.message);
        return send(res, 201, stubForecast(player_id, game_id));
      }
      const player = PLAYERS.find((p) => p.id === player_id);
      const games = GAMES.filter((g) => g.status === "scheduled" && [g.home.team.id, g.away.team.id].includes(player?.team?.id));
      send(res, 200, games.map((g) => player_id === 1001
        ? { game: g, prediction: null, unavailable: tooFew }
        : { game: g, prediction: stubForecast(player_id, g.id), unavailable: null }));
    });
    return;
  }
  const matchupMatch = path.match(/^\/players\/(\d+)\/matchups\/(\d+)$/);
  if (matchupMatch) {
    const opponent = TEAMS.find((t) => t.id === Number(matchupMatch[2]));
    const player = PLAYERS.find((p) => p.id === Number(matchupMatch[1]));
    if (!opponent || !player) return error(res, 404, "team_not_found", "No such team.");
    const meetings = gameLines(player, "2099-00").slice(0, 3).map((l) => ({ ...l, opponent: ref(opponent) }));
    return send(res, 200, {
      player_id: player.id, opponent: ref(opponent), games: 3, wins: 2, losses: 1,
      averages: { pts: 21.5, reb: 6.2, ast: 4.4, fg3m: 1.3, stl: 0.7, blk: 0.3, min: 31.2 },
      fg_pct: 0.48, fg3_pct: 0.36, first_season: "2097-98", last_season: "2099-00", meetings, meta: META,
    });
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
  if (path === "/compare/players") {
    const [a, b] = [q.get("p1"), q.get("p2")].map((v) => PLAYERS.find((p) => p.id === Number(v)));
    if (!a || !b) return error(res, 404, "player_not_found", "No such player.");
    if (a.id === b.id) return error(res, 400, "invalid_parameter", "Pick two different players.");
    const seasonsOf = (p) => (p.is_active ? SEASONS : []);
    const common = seasonsOf(a).filter((x) => seasonsOf(b).includes(x));
    const requested = q.get("season");
    if (requested && !common.includes(requested)) return error(res, 422, "no_common_season", "Not a shared season.");
    const season = requested ?? common[0] ?? null;
    const summaryOf = (p) => ({ id: p.id, full_name: p.full_name, position: p.position, is_active: p.is_active, team: p.team, from_year: p.from_year, to_year: p.to_year });
    if (!season) {
      return send(res, 200, { players: [summaryOf(a), summaryOf(b)], season: null, common_seasons: [], lines: [], axes: [],
        qualified_players: 0, qualification: "", qualified: [false, false], meta: META });
    }
    const line = (p) => ({ ...summary(gameLines(p, season)), season, season_type: "regular" });
    const pool = PLAYERS.filter((p) => p.is_active).map(line);
    const rank = (key, v) => {
      const values = pool.map((l) => (key === "ts_pct" ? l.ts_pct : l.per_game[key]));
      const below = values.filter((x) => x < v).length;
      const equal = values.filter((x) => x === v).length;
      return ((below + 0.5 * equal) / values.length) * 100;
    };
    const lines = [line(a), line(b)];
    const labels = { pts: "Scoring", reb: "Rebounding", ast: "Playmaking", fg3m: "3-point shooting", stl: "Steals", blk: "Blocks", ts_pct: "Efficiency" };
    const axes = Object.entries(labels).map(([key, label]) => {
      const values = lines.map((l) => (key === "ts_pct" ? l.ts_pct : l.per_game[key]));
      return { key, label, values, percentiles: values.map((v) => rank(key, v)) };
    });
    return send(res, 200, {
      players: [summaryOf(a), summaryOf(b)], season, common_seasons: common, lines, axes,
      qualified_players: pool.length,
      qualification: `Ranked against the ${pool.length} players with at least 12 games and 10 minutes per game in ${season}.`,
      qualified: [true, true], meta: META,
    });
  }
  const careerMatch = path.match(/^\/players\/(\d+)\/career$/);
  if (careerMatch) {
    const player = PLAYERS.find((p) => p.id === Number(careerMatch[1]));
    if (!player) return error(res, 404, "player_not_found", "No player with that id.");
    const line = (games, pts, reb, ast, extra = {}) => ({
      games, games_started: games, fg_pct: 0.47, fg3_pct: 0.35, ft_pct: 0.8,
      per_game: { pts, reb, ast, stl: 1.1, blk: 0.4, fg3m: 1.5, tov: 2.0, min: 31.0, ...extra },
    });
    const stint = (t) => ({ abbreviation: t.abbreviation, team: ref(t) });
    const seasons = player.is_active
      ? [{ ...line(60, 21.4, 5.1, 6.3), season: "2099-00", age: 27, teams: [stint(TEAMS[player.id % 2])] }]
      : [
          { ...line(70, 12.5, 3.0, 2.1, { stl: null }), season: "2080-81", age: 22, teams: [stint(TEAMS[0])] },
          { ...line(75, 18.2, 4.4, 3.9), season: "2081-82", age: 23, teams: [stint(TEAMS[1]), { abbreviation: "OLD", team: null }] },
        ];
    const totals = player.is_active ? line(60, 21.4, 5.1, 6.3) : line(145, 15.5, 3.7, 3.0);
    return send(res, 200, {
      player_id: player.id,
      regular: { seasons, totals, partial: player.is_active ? {} : { stl: "2081-82" } },
      playoffs: { seasons: [], totals: null, partial: {} },
      meta: META,
    });
  }
  const match = path.match(/^\/players\/(\d+)(?:\/(stats|trends|games))?$/);
  if (match) return playerRoute(res, Number(match[1]), match[2], q, page);
  return error(res, 404, "not_found", "Resource not found.");
}).listen(PORT, "127.0.0.1", () => console.log(`stub API listening on ${PORT}`));
