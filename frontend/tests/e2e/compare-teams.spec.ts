import { expect, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// tests/e2e/stub-api.mjs: Alpha Ants (1) 2099-00 and 2098-99; Bravo (2) 2099-00 and, as the Old Town
// Owls, 2070-71, a season without turnovers, 3-pointers or ratings.

test.describe("compare teams", () => {
  test("is reachable from the player comparison", async ({ page }) => {
    await page.goto("/compare");
    await page.getByRole("navigation", { name: "Compare" }).getByRole("link", { name: "Teams" }).click();
    await expect(page).toHaveURL("/compare/teams");
    await expect(page.getByText("Pick two team-seasons")).toBeVisible();
  });

  test("picks franchises and seasons into the URL", async ({ page }) => {
    await page.goto("/compare/teams");
    const first = page.getByRole("group", { name: "Team 1" });
    await first.getByLabel("Franchise").selectOption({ label: "Alpha Ants" });
    await expect(page).toHaveURL(/t1=1$/);
    await expect(first.getByLabel("Season")).toHaveValue("2099-00");
    const second = page.getByRole("group", { name: "Team 2" });
    await second.getByLabel("Franchise").selectOption({ label: "Bravo Bears" });
    await expect(page).toHaveURL(/t1=1&s1=2099-00&t2=2$/);
    await second.getByLabel("Season").selectOption("2070-71");
    await expect(page).toHaveURL(/s2=2070-71/);
    await expect(
      page.getByRole("region", { name: "2099-00 Alpha Ants versus 2070-71 Old Town Owls" }),
    ).toBeVisible();
  });

  test("shows unrecorded stats as missing, not zero", async ({ page }) => {
    await page.goto("/compare/teams?t1=1&s1=2099-00&t2=2&s2=2070-71");
    const panel = page.getByRole("region", { name: "Side by side" });
    await expect(panel.getByText("Turnovers", { exact: true })).toBeVisible();
    await expect(panel.getByText("—").first()).toBeVisible();
    await expect(panel.getByText(/did not record it that season/)).toBeVisible();
    await expect(page.getByText("Won the championship")).toBeVisible();
    await expect(page.getByText("Missed the playoffs")).toBeVisible();
  });

  test("swaps sides", async ({ page }) => {
    await page.goto("/compare/teams?t1=1&s1=2099-00&t2=2&s2=2070-71");
    await page.getByRole("button", { name: "Swap teams" }).click();
    await expect(page).toHaveURL(/t1=2&s1=2070-71&t2=1&s2=2099-00/);
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/compare/teams?t1=1&s1=2099-00&t2=2&s2=2070-71");
    await expect(page.getByRole("region", { name: "Side by side" })).toBeVisible();
    await expectAccessible(page);
  });
});
