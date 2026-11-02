import { expect, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// tests/e2e/stub-api.mjs has a final on 2099-11-09 (Alpha 101 at Bravo 112) and scheduled games after it.

test.describe("games", () => {
  test("a game in progress shows its score and clock", async ({ page }) => {
    await page.goto("/games?date=2099-11-07");
    const schedule = page.getByRole("region", { name: "Games by date" });
    const chip = schedule.getByRole("button", { name: /Bravo at Alpha, Live · Q3 5:12/ });
    await expect(chip).toContainText("58");
    await expect(chip).toContainText("61");
    await expect(schedule.getByText("Score updates about once a minute")).toBeVisible();
    await expect(schedule.getByRole("table")).toHaveCount(0);

    await page.goto("/games/0099000100");
    await expect(page.getByText("Live · Q3 5:12")).toBeVisible();
    await expect(page.locator("main").getByText("61", { exact: true })).toBeVisible();
  });

  test("the schedule picks up a new live score without a reload", async ({ page }) => {
    await page.clock.install();
    await page.goto("/games?date=2099-11-07");
    const schedule = page.getByRole("region", { name: "Games by date" });
    await expect(schedule.getByRole("button", { name: /Bravo at Alpha, Live/ })).toBeVisible();
    await page.route("**/api/v1/games?*", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.items[0].home.score = 70;
      await route.fulfill({ response, json: body });
    });
    await page.clock.fastForward(31_000);
    await expect(schedule.getByRole("button", { name: /Bravo at Alpha, Live/ })).toContainText("70");
  });

  test("shows full box scores for a final and keeps the date in the URL", async ({ page }) => {
    await page.goto("/games?date=2099-11-09");
    const schedule = page.getByRole("region", { name: "Games by date" });
    await expect(schedule.getByRole("button", { name: /Alpha at Bravo, Final/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const alpha = schedule.getByRole("table", { name: "Alpha Ants" });
    await expect(alpha.getByRole("row")).toHaveCount(7);
    await expect(alpha.getByRole("row", { name: /^Team / })).toBeVisible();
    await expect(schedule.getByRole("table", { name: "Bravo Bears" })).toBeVisible();

    await schedule.getByRole("button", { name: "Next day" }).click();
    await expect(page).toHaveURL(/date=2099-11-10/);
    await expect(schedule.getByRole("button", { name: /Bravo at Alpha/ })).toBeVisible();
    await expect(schedule.getByRole("table")).toHaveCount(0);
  });

  test("predicts the score of an upcoming game in plain language", async ({ page }) => {
    await page.goto("/games?date=2099-11-10");
    const schedule = page.getByRole("region", { name: "Games by date" });
    await expect(schedule.getByRole("button", { name: /Bravo at Alpha/ })).toContainText("115");
    const forecast = schedule.getByRole("region", { name: "Our prediction" });
    await expect(forecast).toContainText("Ants favored by about 6");
    await expect(forecast).toContainText("Bears 32%");
    await expect(forecast).toContainText("Ants 68%");
    await expect(forecast).toContainText("About 8 in 10 games finish inside these ranges");
    await expectAccessible(page);
  });

  test("explains when an upcoming game has no prediction", async ({ page }) => {
    await page.goto("/games?date=2099-11-12");
    await expect(page.getByText("No score prediction for this game")).toBeVisible();
    await expect(page.getByText(/need 10 earlier games/)).toBeVisible();
  });

  test("an upcoming game has its own page with score forecast and player shortcuts", async ({ page }) => {
    await page.goto("/games?date=2099-11-10");
    const schedule = page.getByRole("region", { name: "Games by date" });
    await schedule.getByRole("link", { name: "Game page" }).click();
    await expect(page).toHaveURL(/\/games\/0099000102$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Bravo Bears at Alpha Ants");
    await expect(page.getByRole("region", { name: "Our prediction" })).toContainText(
      "Ants favored by about 6",
    );
    await expect(page.getByRole("link", { name: "Game page" })).toHaveCount(0);
    const shortcuts = page.getByRole("region", { name: "Predict a player in this game" });
    const alpha = shortcuts.getByRole("list", { name: "Alpha Ants leading scorers" });
    await expect(alpha.getByRole("link")).toHaveCount(3);
    const first = alpha.getByRole("link").first();
    await expect(first).toHaveAttribute("href", /\/predict\?player=\d+&game=0099000102$/);
    await first.click();
    await expect(page).toHaveURL(/\/predict\?player=\d+&game=0099000102$/);
    await expect(page.getByRole("option", { name: /vs Bravo Bears/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  test("a final game page shows the full box score; unknown games are not found", async ({ page }) => {
    await page.goto("/games/0099000101");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Alpha Ants at Bravo Bears");
    await expect(page.getByRole("table", { name: "Alpha Ants" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Predict a player in this game" })).toHaveCount(0);
    await expectAccessible(page);
    await page.goto("/games/0000000001");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Game not found");
  });

  test("a finished game shows the final score next to the pregame prediction", async ({ page }) => {
    await page.goto("/games/0099000101");
    const review = page.getByRole("region", { name: "How our prediction did" });
    await expect(review.getByText("✓ Picked the winner")).toBeVisible();
    await expect(review.getByText("Before tip-off we gave the Bears a 62% chance to win.")).toBeVisible();
    await expect(review.getByRole("listitem").filter({ hasText: "Bears" })).toContainText("112");
    await expect(review.getByRole("listitem").filter({ hasText: "Bears" })).toContainText("Predicted 108");
    await expect(review.getByRole("listitem").filter({ hasText: "Ants" })).toContainText("101");
    await page.goto("/games?date=2099-11-09");
    await expect(page.getByRole("region", { name: "How our prediction did" })).toBeVisible();
  });

  test("ignores a malformed date", async ({ page }) => {
    await page.goto("/games?date=not-a-date");
    await expect(page.getByRole("region", { name: "Games by date" })).toBeVisible();
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/games?date=2099-11-09");
    await expect(page.getByRole("table", { name: "Alpha Ants" })).toBeVisible();
    await expectAccessible(page);
  });
});
