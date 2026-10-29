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
    await expect(page.getByRole("region", { name: "Live accuracy" })).toContainText(
      "No scored predictions yet",
    );
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

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/models");
    await expect(page.getByRole("region", { name: "Accuracy against the baseline" })).toBeVisible();
    await expectAccessible(page);
  });
});
