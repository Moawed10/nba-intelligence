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

  test("jersey numbers and the injury report show on the team page", async ({ page }) => {
    await page.goto("/teams/1");
    await expect(page.getByRole("row", { name: /Zed Fixture/ }).getByText("#1", { exact: true })).toBeVisible();
    const report = page.getByRole("region", { name: "Injury report" });
    await expect(report.getByRole("link", { name: "Test Player 02" })).toBeVisible();
    await expect(report.getByText(/Left hip strain/)).toBeVisible();
    await expect(report.getByText("Out", { exact: true })).toBeVisible();
    await expect(report.getByText(/Return date not updated|Estimated back/)).toBeVisible();
  });

  test("an injured player's profile and forecast say so", async ({ page }) => {
    await page.goto("/players/1002");
    await expect(page.getByText(/Left hip strain/)).toBeVisible();
    await expect(page.getByText(/· #3/)).toBeVisible();
    await page.goto("/predict?player=1002");
    await expect(page.getByText(/This forecast assumes Test plays/)).toBeVisible();
    await expect(page.getByText(/Missing about 18 points a game/)).toBeVisible();
    await expect(page.getByText(/counts players listed as out/)).toBeVisible();
  });

  test("fan posts are attributed, link to the original and say what they are", async ({ page }) => {
    await page.goto("/teams/1");
    const fans = page.getByRole("region", { name: "What people are saying" });
    await expect(fans.getByText(/Synthetic test post/)).toBeVisible();
    const link = fans.getByRole("link", { name: /@fixture\.example\.com/ });
    await expect(link).toHaveAttribute("href", "https://bsky.app/profile/fixture.example.com/post/abc");
    await expect(link).toHaveAttribute("rel", /noopener/);
    await expect(fans.getByText(/isn't a survey of all fans/)).toBeVisible();
  });

  test("home court shows real splits and the home crowd", async ({ page }) => {
    await page.goto("/teams/1");
    const section = page.getByRole("region", { name: "Home court", exact: true });
    await expect(section.getByText("4–1")).toBeVisible();
    await expect(section.getByText("18,200")).toBeVisible();
    const row = section.getByRole("row", { name: /Zed Fixture/ });
    await expect(row.getByRole("cell", { name: "+3.0" })).toBeVisible();
    await page.goto("/predict?player=1000");
    await expect(page.getByText(/averages 25\.5 points at home/)).toBeVisible();
  });
});
