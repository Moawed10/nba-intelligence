import { expect, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

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

  test("lists upcoming games and switches the forecast between them", async ({ page }) => {
    await page.goto("/predict?player=1000");
    const games = page.getByRole("region", { name: "Upcoming games" });
    await expect(games.getByRole("link")).toHaveCount(2);
    await expect(games.getByRole("link", { name: /vs Bravo Bears/ })).toHaveAttribute("aria-current", "true");
    const forecast = page.getByRole("region", { name: "Forecast vs BBB" });
    await expect(forecast.getByText("No model is serving predictions yet")).toBeVisible();
    await expect(forecast.getByText(/2099\.11\.10-1, is a candidate/)).toBeVisible();
    await expect(forecast.getByText("111.9")).toBeVisible();

    await games.getByRole("link", { name: /@ Bravo Bears/ }).click();
    await expect(page).toHaveURL(/game=0099000103/);
    await expect(page.getByRole("region", { name: "Forecast @ BBB" })).toBeVisible();
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
