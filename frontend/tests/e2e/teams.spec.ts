import { expect, test } from "@playwright/test";

test.describe("team page", () => {
  test("a team logo on a player page opens the whole roster with season stats", async ({ page }) => {
    await page.goto("/players/1000");
    await page.getByRole("link", { name: /roster$/ }).first().click();
    await expect(page).toHaveURL(/\/teams\/\d+$/);
    const roster = page.getByRole("region", { name: "Roster" });
    await expect(roster.getByRole("link", { name: "Zed Fixture" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Team stats" }).getByText("Points", { exact: true })).toBeVisible();
    await expect(page.getByText("6–4")).toBeVisible();
  });

  test("a rostered player with no games stays listed, with dashes instead of zeros", async ({ page }) => {
    await page.goto("/players/1000");
    await page.getByRole("link", { name: /roster$/ }).first().click();
    await expect(page).toHaveURL(/\/teams\/\d+$/);
    const row = page.getByRole("row", { name: /Former Fixture/ });
    await expect(row).toBeVisible();
    await expect(row.getByRole("cell", { name: "—" }).first()).toBeVisible();
    await expect(row.getByRole("cell", { name: "0.0" })).toHaveCount(0);
  });

  test("roster columns sort", async ({ page, isMobile }) => {
    test.skip(isMobile, "same table at every width");
    await page.goto("/teams/1");
    const column = page.getByRole("columnheader", { name: /^REB/ });
    await column.getByRole("button").click();
    await expect(column).toHaveAttribute("aria-sort", "descending");
  });

  test("an unknown team shows a not-found page", async ({ page }) => {
    await page.goto("/teams/424242");
    await expect(page.getByRole("heading", { name: "Team not found" })).toBeVisible();
  });

  test("search finds a team by name and opens its page", async ({ page }) => {
    await page.goto("/players");
    const input = page.getByRole("combobox", { name: "Search players and teams" }).first();
    await input.fill("bears");
    await page.getByRole("listbox", { name: /^Matching/ }).getByRole("option", { name: /Bravo Bears/ }).click();
    await expect(page).toHaveURL("/teams/2");
    await expect(page.getByRole("heading", { level: 1, name: "Bravo Bears" })).toBeVisible();
  });
});
