import { writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import queries from "./search-queries.json" with { type: "json" };

// Real data: the backend at LIVE_API_URL with the full stored dataset.
const API = `${process.env.LIVE_API_URL ?? "http://127.0.0.1:8000"}/api/v1`;
const TOP_N = 3;
const LATENCY_SAMPLE = 25;
const PROFILE_SAMPLE = 25;
const AVERAGES = [
  ["pts", "PTS"],
  ["reb", "REB"],
  ["ast", "AST"],
  ["fg3m", "3PM"],
  ["stl", "STL"],
  ["blk", "BLK"],
  ["min", "MIN"],
] as const;

const oneDecimal = (value: number) =>
  value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function percentile(values: number[], pct: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil((pct / 100) * sorted.length) - 1)];
}

function record(name: string, data: unknown) {
  writeFileSync(`test-results/live-${name}.json`, JSON.stringify(data, null, 2));
}

test("search finds the intended player for the 100 documented queries", async ({ request }) => {
  const misses: { query: string; expected: string; got: string[] }[] = [];
  for (const q of queries) {
    const response = await request.get(`${API}/players/search`, { params: { q: q.query, limit: 10 } });
    const results: { id: number; full_name: string }[] = await response.json();
    const top = results.slice(0, TOP_N);
    if (!top.some((r) => r.id === q.expected_id)) {
      misses.push({ query: q.query, expected: q.expected, got: top.map((r) => r.full_name) });
    }
  }
  const relevant = (queries.length - misses.length) / queries.length;
  record("search-relevance", { queries: queries.length, top_n: TOP_N, relevant, misses });
  console.log(`relevant in top ${TOP_N}: ${(relevant * 100).toFixed(1)}%`, misses);
  expect(relevant).toBeGreaterThanOrEqual(0.95);
});

test("search results appear within 500 ms of the last keystroke (p95), one request per query", async ({
  page,
}) => {
  await page.goto("/players");
  const input = page.getByRole("combobox", { name: "Search players" });
  const listbox = page.getByRole("listbox", { name: "Matching players" });
  const timings: number[] = [];
  let searches = 0;
  page.on("request", (r) => {
    if (r.url().includes("/api/v1/players/search")) searches++;
  });

  for (const q of queries.slice(0, LATENCY_SAMPLE)) {
    await input.fill("");
    await expect(listbox).toBeHidden();
    searches = 0;
    await input.pressSequentially(q.query, { delay: 40 });
    const typed = Date.now();
    await expect(listbox.getByRole("option").first()).toBeVisible({ timeout: 5000 });
    timings.push(Date.now() - typed);
    expect(searches, `requests for "${q.query}"`).toBeLessThanOrEqual(1);
  }
  const p95 = percentile(timings, 95);
  record("search-latency", { samples: timings.length, p50: percentile(timings, 50), p95, timings });
  console.log(`search update p50 ${percentile(timings, 50)} ms, p95 ${p95} ms`);
  expect(p95).toBeLessThanOrEqual(500);
});

test("profiles show exactly the statistics the API returns", async ({ page, request }) => {
  const directory = await (
    await request.get(`${API}/players`, { params: { active: true, limit: 100, offset: 0 } })
  ).json();
  const checked: { id: number; name: string; season: string; tiles: number }[] = [];
  for (const player of directory.items as { id: number; full_name: string }[]) {
    if (checked.length >= PROFILE_SAMPLE) break;
    const stats = await (await request.get(`${API}/players/${player.id}/stats`)).json();
    const season = stats.seasons[0];
    if (!season) continue;
    await page.goto(`/players/${player.id}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(player.full_name);
    const averages = page.getByRole("region", { name: `${season.season} regular season` });
    const played = `${season.games_played} ${season.games_played === 1 ? "game" : "games"} played`;
    await expect(averages.getByText(played)).toBeVisible();
    for (const [key, label] of AVERAGES) {
      const tile = averages
        .locator("div")
        .filter({ has: page.locator("dt", { hasText: new RegExp(`^${label}$`) }) });
      await expect(tile.locator("dd").first(), `${player.full_name} ${label}`).toHaveText(
        oneDecimal(season.per_game[key]),
      );
    }
    checked.push({ id: player.id, name: player.full_name, season: season.season, tiles: AVERAGES.length });
  }
  record("profile-match", {
    players: checked.length,
    tiles: checked.reduce((t, c) => t + c.tiles, 0),
    checked,
  });
  expect(checked.length).toBe(PROFILE_SAMPLE);
});
