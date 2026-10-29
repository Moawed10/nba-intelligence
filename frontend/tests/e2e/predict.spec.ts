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
    const list = games.getByRole("listbox", { name: "Upcoming games" });
    await expect(list.getByRole("option")).toHaveCount(2);
    await expect(list.getByRole("option", { name: /vs Bravo Bears/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    const forecast = page.getByRole("region", { name: "Forecast vs BBB" });
    await forecast.getByRole("button", { name: "Make forecast" }).click();
    await expect(
      forecast.getByRole("img", { name: /^Points: predicted 24\.0, likely range 16\.0 to 32\.0/ }),
    ).toBeVisible();
    await expect(forecast.getByText("25%")).toBeVisible();
    await expect(forecast.getByText("Up to date")).toBeVisible();
    await expect(forecast.getByText(/Inputs: last 5 23\.0 · last 10 22\.0/)).toBeVisible();
    await expect(forecast.getByText("111.9")).toBeVisible();

    await list.getByRole("option", { name: /@ Bravo Bears/ }).click();
    await expect(page).toHaveURL(/game=0099000103/);
    await expect(page.getByRole("region", { name: "Forecast @ BBB" })).toBeVisible();
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

  test("explains when a player has too few games for a forecast", async ({ page }) => {
    await page.goto("/predict?player=1001");
    const forecast = page.getByRole("region", { name: /^Forecast/ });
    await forecast.getByRole("button", { name: "Make forecast" }).click();
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
