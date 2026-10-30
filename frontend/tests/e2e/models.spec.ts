import { expect, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// Release 2099.11.10-1 in tests/e2e/stub-api.mjs: pts (XGBoost), reb (Ridge) and a double-double classifier.

test.describe("models", () => {
  test("shows the release, its held-out accuracy and that it is serving", async ({ page }) => {
    await page.goto("/models");
    const release = page.getByRole("region", { name: "2099.11.10-1" });
    await expect(release.getByText("Serving predictions")).toBeVisible();
    await expect(release.getByText("Test · 2096-97")).toBeVisible();
    const accuracy = page.getByRole("region", { name: "Accuracy against the baseline" });
    await expect(accuracy.getByRole("row", { name: /Points XGBoost 4\.50 4\.70 4\.3%/ })).toBeVisible();
    await expect(accuracy.getByRole("row", { name: /Rebounds Ridge regression 1\.90 1\.95/ })).toBeVisible();
    const live = page.getByRole("region", { name: "Live accuracy", exact: true });
    await expect(live.getByRole("row", { name: /Points 5\.25 4\.50 83\.3% 6/ })).toBeVisible();
    await expect(live.getByText(/across 2 games/)).toBeVisible();
  });

  test("ranks candidate algorithms by validation error", async ({ page }) => {
    await page.goto("/models");
    const comparison = page.getByRole("region", { name: "Algorithm comparison" });
    const rows = comparison.getByRole("table").getByRole("row");
    await expect(rows.nth(1)).toContainText("XGBoost");
    await expect(rows.nth(1)).toContainText("Selected");
    await expect(rows.nth(3)).toContainText("Baseline (last 10 games)");
    await expect(rows.nth(3)).toContainText("Reference");
  });

  test("states prediction ranges and the double-double scores", async ({ page }) => {
    await page.goto("/models");
    const ranges = page.getByRole("region", { name: "Prediction ranges" });
    await expect(ranges.getByRole("row", { name: "Points ±3.0 ±5.0 ±7.0" })).toBeVisible();
    await expect(ranges.getByText(/held 80%–81% of results/)).toBeVisible();
    const dd = page.getByRole("region", { name: "Double-double" });
    await expect(dd.getByText("0.050")).toBeVisible();
    await expect(dd.getByText("Logistic regression with isotonic calibration")).toBeVisible();
  });

  test("falls back to the latest release for an unknown version", async ({ page }) => {
    await page.goto("/models?version=2000.01.01-1");
    await expect(page.getByText("No release named 2000.01.01-1")).toBeVisible();
    await expect(page.getByRole("region", { name: "2099.11.10-1" })).toBeVisible();
  });

  test("lists every input feature on request", async ({ page }) => {
    await page.goto("/models");
    await page.getByText("Show all 3 inputs").click();
    await expect(page.getByText("rest_days", { exact: true })).toBeVisible();
  });

  test("section navigator jumps to a panel on wide screens", async ({ page }, info) => {
    test.skip(!info.project.name.startsWith("desktop"), "the navigator shows at 1280 px and wider");
    await page.goto("/models");
    const nav = page.getByRole("complementary", { name: "Model sections" });
    await nav.getByRole("button", { name: "Releases" }).click();
    await expect(page.getByRole("heading", { name: "Releases" })).toBeInViewport();
  });

  test("checks every stored prediction against the result, labelled as a backtest", async ({ page }) => {
    await page.goto("/models");
    const check = page.getByRole("region", { name: "Check the predictions" });
    await expect(check.getByText(/Backtest: made after the fact/)).toBeVisible();
    await expect(check.getByText("1,000")).toBeVisible();
    await expect(check.getByText("80%").first()).toBeVisible();
    await expect(check.getByRole("region", { name: "Predicted vs. actual" })).toBeVisible();
    await expect(check.getByText(/never more than 0\.2 points/)).toBeVisible();
    await expect(check.getByText(/at least 79% in every group/)).toBeVisible();
    await check.getByRole("radio", { name: "REB" }).click();
    await expect(check.getByText(/never more than 0\.1 rebounds/)).toBeVisible();
    await check.getByRole("radio", { name: "Live" }).click();
    await expect(check.getByText("No live predictions scored yet")).toBeVisible();
  });

  test("history explorer shows a player's predictions next to the results", async ({ page }) => {
    await page.goto("/models");
    const explorer = page.getByRole("region", { name: "Prediction history" });
    await expect(explorer.getByText("Pick a player")).toBeVisible();
    await explorer.getByRole("combobox").fill("zed");
    await page.getByRole("option", { name: /Zed Fixture/ }).click();
    await expect(explorer.getByText(/inside the predicted range in 1 of the 2 scored games/)).toBeVisible();
    const table = explorer.getByRole("table");
    await expect(table.locator("tbody tr")).toHaveCount(2);
    await expect(table.locator("tbody tr").first()).toContainText("inside the range");
    await explorer.getByRole("radio", { name: "Live" }).click();
    await expect(explorer.getByText("No pregame predictions for Zed Fixture")).toBeVisible();
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/models");
    await expect(page.getByRole("region", { name: "Accuracy against the baseline" })).toBeVisible();
    await expectAccessible(page);
  });
});
