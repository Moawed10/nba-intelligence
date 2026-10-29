import { expect, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// tests/e2e/stub-api.mjs has a final on 2099-11-09 (Alpha 101 at Bravo 112) and scheduled games after it.

test.describe("games", () => {
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
