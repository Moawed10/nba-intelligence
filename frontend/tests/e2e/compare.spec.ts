import { expect, type Page, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

const STUB = `http://127.0.0.1:${process.env.STUB_API_PORT ?? 8799}/api/v1`;

// Players 1000 ("Zed Fixture") and 1001 come from tests/e2e/stub-api.mjs; 1990 is a former player with no seasons.

async function pick(page: Page, slot: "Player 1" | "Player 2", query: string, name: string) {
  await page.getByRole("combobox", { name: slot }).fill(query);
  await page
    .getByRole("listbox")
    .getByRole("option", { name: new RegExp(name) })
    .click();
}

test.describe("compare", () => {
  test("builds a comparison from two searches and keeps it in the URL", async ({ page }) => {
    await page.goto("/compare");
    await expect(page.getByText("Pick two players")).toBeVisible();
    await pick(page, "Player 1", "zed", "Zed Fixture");
    await expect(page).toHaveURL(/\/compare\?p1=1000$/);
    await expect(page.getByText("Pick a second player")).toBeVisible();
    await pick(page, "Player 2", "player 01", "Test Player 01");
    await expect(page).toHaveURL(/p1=1000&p2=1001/);
    await expect(
      page.getByRole("region", { name: "Zed Fixture versus Test Player 01, 2099-00" }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Head to head" })).toContainText("Points");
  });

  test("swaps sides, changes season and removes a player", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1001");
    await page.getByRole("button", { name: "Swap players" }).click();
    await expect(page).toHaveURL(/p1=1001&p2=1000&season=2099-00/);
    await expect(page.getByRole("region", { name: /^Test Player 01 versus Zed Fixture/ })).toBeVisible();

    await page.getByRole("combobox", { name: "Season" }).selectOption("2098-99");
    await expect(page).toHaveURL(/season=2098-99/);
    await expect(page.getByRole("region", { name: /2098-99$/ })).toBeVisible();

    await page.getByRole("button", { name: "Remove Zed Fixture" }).click();
    await expect(page).toHaveURL(/\/compare\?p1=1001$/);
    await expect(page.getByText("Pick a second player")).toBeVisible();
  });

  test("refuses the same player twice", async ({ page }) => {
    await page.goto("/compare?p1=1000");
    await pick(page, "Player 2", "zed", "Zed Fixture");
    await expect(page.getByRole("status").filter({ hasText: "already in the other slot" })).toBeVisible();
    await expect(page).toHaveURL(/\/compare\?p1=1000$/);
  });

  test("explains players without a shared season and unknown ids", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1990");
    await expect(page.getByText("These players never played in the same season")).toBeVisible();
    await page.goto("/compare?p1=99999&p2=1000");
    await expect(page.getByText("A player in this link wasn't found")).toBeVisible();
    await expect(page.getByText("Pick a second player")).toBeVisible();
  });

  test("form chart switches statistic and has a table equivalent", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1001");
    const form = page.getByRole("region", { name: "Form" });
    await expect(
      form.getByText(/Zed Fixture averages [\d.]+ and Test Player 01 [\d.]+ points per game/),
    ).toBeVisible();
    await form.getByRole("radio", { name: "REB" }).click();
    await expect(form.getByText(/rebounds per game, over 30 and 30 games/)).toBeVisible();
    await form.getByRole("radio", { name: "Table" }).click();
    await expect(form.getByRole("table").getByRole("row")).toHaveCount(31);
  });

  test("ranks both players against the league with a table equivalent", async ({ page, request }) => {
    const api = await (await request.get(`${STUB}/compare/players?p1=1000&p2=1001`)).json();
    await page.goto("/compare?p1=1000&p2=1001");
    const radar = page.getByRole("region", { name: "League ranking by area" });
    await expect(radar.getByText(/ranks higher in \d of 7 areas/)).toBeVisible();
    await expect(page.getByText(/Ranked against the 30 players/)).toBeVisible();
    await radar.getByRole("radio", { name: "Table" }).click();
    const table = radar.getByRole("table");
    await expect(table.locator("tbody tr")).toHaveCount(7);
    const scoring = api.axes[0];
    const ordinal = (n: number) => {
      const r = Math.round(n);
      const suffix = r % 100 >= 11 && r % 100 <= 13 ? "th" : (["th", "st", "nd", "rd"][r % 10] ?? "th");
      return `${r}${suffix} percentile`;
    };
    await expect(table.locator("tbody tr").first()).toContainText(ordinal(scoring.percentiles[0]));
    await expect(table.locator("tbody tr").first()).toContainText(ordinal(scoring.percentiles[1]));
  });

  test("chart and table toggles respond within 200 ms (p95 over 20)", async ({ page, isMobile }) => {
    test.skip(isMobile, "timed once, on desktop");
    await page.goto("/compare?p1=1000&p2=1001");
    const radar = page.getByRole("region", { name: "League ranking by area" });
    await radar.getByRole("figure").waitFor();
    const timings: number[] = [];
    for (let i = 0; i < 20; i++) {
      const toTable = i % 2 === 0;
      const started = await page.evaluate(() => performance.now());
      await radar.getByRole("radio", { name: toTable ? "Table" : "Chart" }).click();
      await (toTable ? radar.getByRole("table") : radar.getByRole("figure")).waitFor();
      timings.push((await page.evaluate(() => performance.now())) - started);
    }
    timings.sort((x, y) => x - y);
    const p95 = timings[Math.ceil(timings.length * 0.95) - 1];
    test.info().annotations.push({ type: "toggle p95 ms", description: p95.toFixed(0) });
    expect(p95).toBeLessThanOrEqual(200);
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1001");
    await expect(page.getByRole("region", { name: "Head to head" })).toBeVisible();
    await expectAccessible(page);
  });
});
