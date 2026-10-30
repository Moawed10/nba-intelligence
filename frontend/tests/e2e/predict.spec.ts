import { expect, type Locator, type Page, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

const STUB = `http://127.0.0.1:${process.env.STUB_API_PORT ?? 8799}/api/v1`;

/** Presses Tab until the target has focus, as a keyboard-only user would. */
async function tabTo(page: Page, target: Locator, limit = 60) {
  for (let i = 0; i < limit; i++) {
    if (await target.evaluate((el) => el === document.activeElement || el.contains(document.activeElement)))
      return;
    await page.keyboard.press("Tab");
  }
  throw new Error("target never received focus from the keyboard");
}

// tests/e2e/stub-api.mjs: Zed Fixture (1000) plays for Alpha, scheduled vs Bravo on 2099-11-10 and at Bravo on 2099-11-12.

test.describe("predictions", () => {
  test("starts from search or a scoring leader", async ({ page }) => {
    await page.goto("/predict");
    await expect(page.getByText("Or start with a 2099-00 scoring leader")).toBeVisible();
    await page.getByRole("combobox", { name: "Player" }).fill("zed");
    await page
      .getByRole("listbox")
      .getByRole("option", { name: /Zed Fixture/ })
      .click();
    await expect(page).toHaveURL(/\/predict\?player=1000$/);
    await expect(page.getByRole("heading", { name: "Zed Fixture" })).toBeVisible();
  });

  test("forecasts every upcoming game and explains it in plain language", async ({ page }) => {
    await page.goto("/predict?player=1000");
    const games = page.getByRole("region", { name: "Upcoming games" });
    const list = games.getByRole("listbox", { name: "Upcoming games" });
    await expect(list.getByRole("option")).toHaveCount(2);
    await expect(list.getByRole("option", { name: /vs Bravo Bears/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(list.getByRole("option", { name: /@ Bravo Bears.*26/ })).toBeVisible();

    const forecast = page.getByRole("region", { name: "Forecast vs BBB" });
    await expect(forecast.getByText(/expected to score about 24 points/)).toBeVisible();
    await expect(forecast.getByText("Usually 16–32")).toBeVisible();
    await expect(forecast.getByText("25%")).toBeVisible();
    await expect(forecast.getByText(/In 3 games since 2097-98/)).toBeVisible();
    await expect(forecast.getByText("111.9")).toBeVisible();
    await forecast.getByText("What is this based on?").click();
    await expect(forecast.getByText(/Recent games\s*23/)).toBeVisible();
  });

  test("switching games replaces the forecast instead of keeping the previous one", async ({ page }) => {
    await page.goto("/predict?player=1000");
    await expect(
      page.getByRole("region", { name: "Forecast vs BBB" }).getByText(/about 24 points/),
    ).toBeVisible();
    const list = page.getByRole("listbox", { name: "Upcoming games" });
    await list.getByRole("option", { name: /@ Bravo Bears/ }).click();
    await expect(page).toHaveURL(/game=0099000103/);
    const second = page.getByRole("region", { name: "Forecast @ BBB" });
    await expect(second.getByText(/about 26 points/)).toBeVisible();
    await expect(second.getByText(/about 24 points/)).toHaveCount(0);
  });

  test("upcoming games can be chosen with the keyboard", async ({ page, isMobile }) => {
    test.skip(isMobile, "keyboard flow is covered on pointer devices");
    await page.goto("/predict?player=1000");
    const list = page.getByRole("listbox", { name: "Upcoming games" });
    await list.focus();
    await page.keyboard.press("ArrowDown");
    await expect(list.getByRole("option", { name: /@ Bravo Bears/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/game=0099000103/);
  });

  test("plots the forecast range over the player's real recent games", async ({ page, request }) => {
    const log = await (await request.get(`${STUB}/players/1000/games?season_type=regular&limit=20`)).json();
    const points: number[] = log.items.map((g: { box: { pts: number } }) => g.box.pts);
    const inside = points.filter((v) => v >= 16 && v <= 32).length;
    await page.goto("/predict?player=1000");
    const chart = page.getByRole("region", { name: `This forecast vs. the last ${points.length} games` });
    await expect(
      chart.getByText(
        `Zed finished between 16 and 32 points, the range expected for this game, in ${inside} of the last ${points.length} games.`,
      ),
    ).toBeVisible();
    await expect(chart.locator("circle")).toHaveCount(points.length);
    await chart.getByRole("radio", { name: "Rebounds" }).click();
    await expect(chart.getByText(/between 4 and 10 rebounds/)).toBeVisible();
  });

  test("the whole workflow works with the keyboard alone", async ({ page, isMobile }) => {
    test.skip(isMobile, "keyboard flow is covered on pointer devices");
    await page.goto("/predict");
    const search = page.getByRole("combobox", { name: "Player" });
    await tabTo(page, search);
    await page.keyboard.type("zed");
    await expect(page.getByRole("option", { name: /Zed Fixture/ })).toBeVisible();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/predict\?player=1000$/);

    const list = page.getByRole("listbox", { name: "Upcoming games" });
    await tabTo(page, list);
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/game=0099000103/);
    const forecast = page.getByRole("region", { name: "Forecast @ BBB" });
    await expect(forecast.getByText(/about 26 points/)).toBeVisible();

    const points = forecast.getByRole("radio", { name: "Points" });
    await tabTo(page, points);
    await page.keyboard.press("ArrowRight");
    await expect(forecast.getByRole("radio", { name: "Rebounds" })).toBeChecked();
    await expect(forecast.getByText(/rebounds, the range expected/)).toBeVisible();

    const details = forecast.getByText("What is this based on?");
    await tabTo(page, details);
    await page.keyboard.press("Enter");
    await expect(forecast.getByText(/Recent games\s*23/)).toBeVisible();
  });

  test("a forecast renders within 500 ms of its response (p95 over 20 switches)", async ({
    page,
    isMobile,
  }) => {
    test.skip(isMobile, "timed once, on desktop");
    test.setTimeout(120_000);
    await page.goto("/predict?player=1000");
    const list = page.getByRole("listbox", { name: "Upcoming games" });
    const timings: number[] = [];
    for (let i = 0; i < 20; i++) {
      const [name, region, text, id] =
        i % 2 === 0
          ? [/@ Bravo Bears/, "Forecast @ BBB", /about 26 points/, "0099000103"]
          : [/vs Bravo Bears/, "Forecast vs BBB", /about 24 points/, "0099000102"];
      const response = page.waitForResponse((r) => r.url().includes(`game=${id}`));
      await list.getByRole("option", { name }).click();
      await response;
      const received = await page.evaluate(() => performance.now());
      await page.getByRole("region", { name: region }).getByText(text).waitFor();
      timings.push((await page.evaluate(() => performance.now())) - received);
    }
    timings.sort((a, b) => a - b);
    const p95 = timings[Math.ceil(timings.length * 0.95) - 1];
    test.info().annotations.push({ type: "render p95 ms", description: p95.toFixed(0) });
    expect(p95).toBeLessThanOrEqual(500);
  });

  test("explains when a player has too few games for a forecast", async ({ page }) => {
    await page.goto("/predict?player=1001");
    const forecast = page.getByRole("region", { name: /^Forecast/ });
    await expect(forecast.getByText("Not enough recent games for a forecast")).toBeVisible();
  });

  test("explains players without games and unknown ids", async ({ page }) => {
    await page.goto("/predict?player=1990");
    await expect(page.getByText("No games in the next 14 days")).toBeVisible();
    await expect(page.getByText("This player isn't on a current roster.")).toBeVisible();
    await page.goto("/predict?player=99999");
    await expect(page.getByText("No player has id 99999")).toBeVisible();
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/predict?player=1000");
    await expect(page.getByRole("region", { name: "Forecast vs BBB" })).toBeVisible();
    await expectAccessible(page);
  });
});
