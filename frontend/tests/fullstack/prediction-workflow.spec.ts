import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

import { FULLSTACK_ENV } from "../../playwright.fullstack.config";

const BACKEND = path.resolve(__dirname, "../../../backend");
const PYTHON = process.env.FULLSTACK_PYTHON ?? ".venv/bin/python";
const scenario = JSON.parse(readFileSync(path.join(BACKEND, "tests/fullstack/scenario.json"), "utf8"));

type Line = { pts: number; reb: number; ast: number };
type Game = { number: number; lines: Record<string, Line> };
type StoredPrediction = {
  id: string;
  player_id: number;
  game_id: string;
  created_at: string;
  supersedes: string | null;
  sha: string;
  values: Record<string, { point: number; lower: number; upper: number }>;
  evaluations: Record<string, { actual: number; abs_error: number; within: boolean | null }> | null;
};
type State = {
  predictions: StoredPrediction[];
  target: { status: string; stats_finalized_at: string | null };
};

const gameId = (number: number) => `00299${String(number).padStart(5, "0")}`;
const TARGET = gameId(scenario.target.number);
const LATER = gameId(scenario.later[0].number);
const STAR: number = scenario.star;
const OTHER: number = scenario.opponent_player;
const VERSION: string = scenario.version;
const API = "/api/v1";

function harness<T>(...args: string[]): T {
  const output = execFileSync(PYTHON, ["-m", "tests.fullstack.harness", ...args], {
    cwd: BACKEND,
    env: { ...process.env, ...FULLSTACK_ENV },
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  return JSON.parse(output) as T;
}

const state = () => harness<State>("state");
const rowsFor = (s: State, player: number, game: string) =>
  s.predictions.filter((p) => p.player_id === player && p.game_id === game);

const mean = (values: number[]) => values.reduce((sum, v) => sum + v, 0) / values.length;

function starPoints(games: Game[]): number[] {
  return games.map((g) => g.lines[String(STAR)]?.pts).filter((v): v is number => v !== undefined);
}

function intervalHalfWidth(predictedMinutes: number): number {
  const edges: number[] = scenario.conformal.edges;
  const bin = edges.filter((edge) => predictedMinutes >= edge).length;
  return scenario.conformal.quantiles[bin];
}

const HALF_WIDTH = intervalHalfWidth(48);
const FIRST_POINT = mean(starPoints(scenario.finals).slice(-10));
const REFRESHED_POINT = mean(starPoints([...scenario.finals, scenario.added_final]).slice(-10));
const STAR_ACTUAL: Line = scenario.target.lines[String(STAR)];
const OTHER_POINT: number = scenario.default_line.pts;
const OTHER_ACTUAL: Line = scenario.target.lines[String(OTHER)];
const STAR_MISS = Math.abs(REFRESHED_POINT - STAR_ACTUAL.pts);
const OTHER_MISS = Math.abs(OTHER_POINT - OTHER_ACTUAL.pts);
const LIVE_MAE = mean([STAR_MISS, OTHER_MISS]);
const LIVE_RMSE = Math.sqrt(mean([STAR_MISS ** 2, OTHER_MISS ** 2]));
const LIVE_COVERAGE = mean([STAR_MISS <= HALF_WIDTH ? 1 : 0, OTHER_MISS <= HALF_WIDTH ? 1 : 0]);
const PRIOR: number = scenario.double_double_prior;
const STAR_DOUBLE = STAR_ACTUAL.pts >= 10 && STAR_ACTUAL.reb >= 10 ? 1 : 0;
const OTHER_DOUBLE = OTHER_ACTUAL.pts >= 10 && OTHER_ACTUAL.reb >= 10 ? 1 : 0;
const LIVE_BRIER = mean([(PRIOR - STAR_DOUBLE) ** 2, (PRIOR - OTHER_DOUBLE) ** 2]);

const BACKTEST_ROWS = 10;
const STAR_GAMES = starPoints(scenario.finals);
const BACKTEST_STAR_MISS = Math.abs(mean(STAR_GAMES.slice(0, 5)) - STAR_GAMES[5]);
const BACKTEST_MAE = BACKTEST_STAR_MISS / BACKTEST_ROWS;
const BACKTEST_COVERAGE = (BACKTEST_ROWS - (BACKTEST_STAR_MISS > HALF_WIDTH ? 1 : 0)) / BACKTEST_ROWS;

type ApiValue = { stat: string; point: number; lower: number; upper: number };
type ApiPrediction = {
  id: string;
  freshness: string;
  supersedes_prediction_id: string | null;
  actuals: Record<string, number> | null;
  values: ApiValue[];
  created_at: string;
};

async function predictions(request: APIRequestContext, player: number, game: string) {
  const response = await request.get(`${API}/predictions`, { params: { player_id: player, game_id: game } });
  expect(response.ok()).toBe(true);
  return (await response.json()) as ApiPrediction[];
}

const stat = (row: ApiPrediction, name: string) => row.values.find((v) => v.stat === name)!;

const forecastPanel = (page: Page) => page.getByRole("region", { name: /^Forecast/ });

async function openForecast(page: Page, player: number, game: string) {
  await page.goto(`/predict?player=${player}&game=${game}`);
  await expect(forecastPanel(page)).toBeVisible();
}

test("a forecast goes from creation through refresh, tip-off, the final box score and scoring", async ({
  page,
  request,
}) => {
  const external: string[] = [];
  page.on("request", (r) => {
    const host = new URL(r.url()).hostname;
    if (r.url().startsWith("http") && host !== "localhost") external.push(r.url());
  });

  await test.step("the suite talks to the real API with the controlled clock", async () => {
    expect(rowsFor(state(), STAR, TARGET)).toEqual([]);
    const live = await (await request.get(`${API}/models/${VERSION}/live`)).json();
    expect(live.games).toBe(0);
    expect(live.status).toBe("active");
  });

  await test.step("1-2: find the player and open the profile", async () => {
    await page.goto("/players");
    const search = page.getByRole("combobox", { name: "Search players" });
    await search.fill("Testić");
    const results = page.getByRole("listbox", { name: "Matching players" });
    await results.getByRole("option", { name: /Nikola Testić/ }).click();
    await expect(page).toHaveURL(new RegExp(`/players/${STAR}`));
    await expect(page.getByRole("heading", { level: 1, name: "Nikola Testić" })).toBeVisible();
  });

  await test.step("3-4: choose an eligible scheduled game; opening it creates the forecast", async () => {
    await page.getByRole("link", { name: "Predict next game" }).click();
    await expect(page).toHaveURL(new RegExp(`/predict\\?player=${STAR}`));
    const games = page.getByRole("listbox", { name: "Upcoming games" });
    await games.getByRole("option", { name: /@ Charlie Cats/ }).click();
    await expect(page).toHaveURL(new RegExp(`game=${LATER}`));
    await games.getByRole("option", { name: /vs Bravo Bears/ }).click();
    await expect(page).toHaveURL(new RegExp(`game=${TARGET}`));
    await expect(forecastPanel(page)).toContainText(FIRST_POINT.toFixed(1));

    const rows = rowsFor(state(), STAR, TARGET);
    expect(rows).toHaveLength(1);
    expect(rows[0].values.pts.point).toBeCloseTo(FIRST_POINT, 9);
    expect(rows[0].values.pts.lower).toBeCloseTo(FIRST_POINT - HALF_WIDTH, 9);
    expect(rows[0].values.pts.upper).toBeCloseTo(FIRST_POINT + HALF_WIDTH, 9);
    expect(rows[0].supersedes).toBeNull();
  });

  const original = rowsFor(state(), STAR, TARGET)[0];

  await test.step("5: the stored forecast is still there after a reload", async () => {
    await page.reload();
    await expect(forecastPanel(page)).toContainText(FIRST_POINT.toFixed(1));
    const stored = await predictions(request, STAR, TARGET);
    expect(stored.map((r) => r.id)).toEqual([original.id]);
    expect(stored[0].freshness).toBe("current");
  });

  await test.step("6: repeating the request reuses the row for the same inputs", async () => {
    const repeat = await request.post(`${API}/predictions`, { data: { player_id: STAR, game_id: TARGET } });
    expect(repeat.status()).toBe(200);
    expect((await repeat.json()).id).toBe(original.id);
    await openForecast(page, STAR, TARGET);
    expect(rowsFor(state(), STAR, TARGET)).toEqual([original]);
  });

  await test.step("7-9: an earlier game arrives, maintenance appends a superseding forecast", async () => {
    harness("add-game");
    const [stale] = await predictions(request, STAR, TARGET);
    expect(stale.freshness).toBe("stale");

    const first = harness<{ refreshed: number }>("maintain");
    expect(first.refreshed).toBe(1);
    const second = harness<{ refreshed: number }>("maintain");
    expect(second.refreshed).toBe(0);

    const rows = rowsFor(state(), STAR, TARGET);
    expect(rows).toHaveLength(2);
    const replacement = rows.find((r) => r.id !== original.id)!;
    expect(rows.find((r) => r.id === original.id)).toEqual(original);
    expect(replacement.supersedes).toBe(original.id);
    expect(replacement.sha).not.toBe(original.sha);
    expect(replacement.values.pts.point).toBeCloseTo(REFRESHED_POINT, 9);

    const stored = await predictions(request, STAR, TARGET);
    const byId = new Map(stored.map((r) => [r.id, r]));
    expect(byId.get(original.id)!.freshness).toBe("superseded");
    expect(byId.get(replacement.id)!.freshness).toBe("current");

    await openForecast(page, STAR, TARGET);
    await expect(forecastPanel(page)).toContainText(REFRESHED_POINT.toFixed(1));
    expect(rowsFor(state(), STAR, TARGET)).toHaveLength(2);

    await openForecast(page, OTHER, TARGET);
    const other = rowsFor(state(), OTHER, TARGET);
    expect(other).toHaveLength(1);
    expect(other[0].values.pts.point).toBeCloseTo(OTHER_POINT, 9);
  });

  const beforeTipoff = state();

  await test.step("10: past tip-off new pregame forecasts are refused", async () => {
    harness("clock", scenario.clock.after_tipoff);
    const refused = await request.post(`${API}/predictions`, { data: { player_id: STAR, game_id: TARGET } });
    expect(refused.status()).toBe(409);
    expect((await refused.json()).error.code).toBe("game_already_started");

    await page.goto(`/predict?player=${STAR}&game=${TARGET}`);
    await expect(forecastPanel(page)).toContainText("This game has started");
    await expect(forecastPanel(page)).not.toContainText("is expected to score");

    harness("maintain");
    expect(rowsFor(state(), STAR, TARGET)).toEqual(rowsFor(beforeTipoff, STAR, TARGET));
    const stored = await predictions(request, STAR, TARGET);
    expect(stored.find((r) => r.id !== original.id)!.freshness).toBe("final_pregame");
  });

  await test.step("11: the game finishes and the box score is ingested", async () => {
    harness("clock", scenario.clock.after_final);
    const finalized = harness<{ finalized: number; events: number }>("finalize");
    expect(finalized.finalized).toBeGreaterThan(0);
    expect(state().target.status).toBe("final");
    expect(state().target.stats_finalized_at).not.toBeNull();
  });

  await test.step("12: scoring is written once, and repeating it changes nothing", async () => {
    const scored = state();
    expect(rowsFor(scored, STAR, TARGET).every((r) => r.evaluations !== null)).toBe(true);
    const again = harness<{ pending: number; maintenance: { scored: number } }>("score");
    expect(again.pending).toBe(0);
    expect(again.maintenance.scored).toBe(0);
    const targetRows = (s: State) => s.predictions.filter((p) => p.game_id === TARGET);
    expect(targetRows(state())).toEqual(targetRows(scored));
  });

  await test.step("13: actuals and evaluation metrics match the fixture", async () => {
    const rows = rowsFor(state(), STAR, TARGET);
    const final = rows.find((r) => r.id !== original.id)!;
    expect(final.evaluations!.pts.actual).toBe(STAR_ACTUAL.pts);
    expect(final.evaluations!.pts.abs_error).toBeCloseTo(STAR_MISS, 9);
    expect(final.evaluations!.pts.within).toBe(STAR_MISS <= HALF_WIDTH);
    expect(final.values).toEqual(rowsFor(beforeTipoff, STAR, TARGET).find((r) => r.id === final.id)!.values);
    expect(rows.find((r) => r.id === original.id)!.values).toEqual(original.values);

    const stored = await predictions(request, STAR, TARGET);
    expect(stored.every((r) => r.actuals?.pts === STAR_ACTUAL.pts)).toBe(true);
    expect(
      stat(
        stored.find((r) => r.id === original.id)!,
        "pts",
      ).point,
    ).toBeCloseTo(FIRST_POINT, 9);

    const history = await (
      await request.get(`${API}/predictions/history`, {
        params: { player_id: STAR, kind: "pregame", limit: 30 },
      })
    ).json();
    const entry = history.entries.find((e: { game_id: string }) => e.game_id === TARGET);
    expect(entry.prediction_id).toBe(final.id);
    expect(entry.values.pts.actual).toBe(STAR_ACTUAL.pts);
    expect(entry.values.pts.point).toBeCloseTo(REFRESHED_POINT, 9);

    await page.goto("/models");
    const explorer = page.getByRole("region", { name: "Prediction history", exact: true });
    await explorer.getByRole("combobox", { name: "Player" }).fill("Testić");
    await page
      .getByRole("listbox")
      .getByRole("option", { name: /Nikola Testić/ })
      .click();
    await explorer.getByRole("radio", { name: "Live" }).click();
    const row = explorer.locator("tbody tr").filter({ hasText: "vs BBB" });
    await expect(row).toContainText(REFRESHED_POINT.toFixed(1));
    await expect(row).toContainText(String(STAR_ACTUAL.pts));
  });

  await test.step("14: live analytics count each player-game once and stay apart from backtests", async () => {
    const live = await (await request.get(`${API}/models/${VERSION}/live`)).json();
    expect(live.games).toBe(1);
    const pts = live.stats.find((s: { stat: string }) => s.stat === "pts");
    expect(pts.n).toBe(2);
    expect(pts.mae).toBeCloseTo(LIVE_MAE, 9);
    expect(pts.interval_coverage).toBeCloseTo(LIVE_COVERAGE, 9);
    expect(live.double_double.n).toBe(2);
    expect(live.double_double.brier).toBeCloseTo(LIVE_BRIER, 9);

    const pregame = await (
      await request.get(`${API}/models/${VERSION}/analytics`, { params: { stat: "pts", kind: "pregame" } })
    ).json();
    expect(pregame.n).toBe(2);
    expect(pregame.mae).toBeCloseTo(LIVE_MAE, 9);
    expect(pregame.rmse).toBeCloseTo(LIVE_RMSE, 9);
    expect(pregame.coverage).toBeCloseTo(LIVE_COVERAGE, 9);

    const backtest = await (
      await request.get(`${API}/models/${VERSION}/analytics`, { params: { stat: "pts", kind: "backtest" } })
    ).json();
    expect(backtest.n).toBe(BACKTEST_ROWS);
    expect(backtest.mae).toBeCloseTo(BACKTEST_MAE, 9);
    expect(backtest.coverage).toBeCloseTo(BACKTEST_COVERAGE, 9);

    await page.goto("/models");
    const table = page.getByRole("region", { name: "Live accuracy by statistic" });
    const row = table.getByRole("row", { name: /^Points/ });
    await expect(row).toContainText(LIVE_MAE.toFixed(2));
    await expect(page.getByRole("region", { name: "Live accuracy", exact: true })).toContainText(
      "across 1 game",
    );
    await expect(page.getByRole("region", { name: "Live accuracy", exact: true })).toContainText(
      `Brier score ${LIVE_BRIER.toFixed(3)} over 2 forecasts`,
    );

    const check = page.getByRole("region", { name: "Check the predictions", exact: true });
    await check.getByRole("radio", { name: "Live" }).click();
    await expect(check.getByText("Games checked").locator("..")).toContainText("2");
    await expect(check.getByText("Average miss").locator("..")).toContainText(LIVE_MAE.toFixed(1));
  });

  expect(external).toEqual([]);
});
