import { expect, type Page, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// Server-rendered pages read from tests/e2e/stub-api.mjs (synthetic season 2099-00).
const STUB = "http://127.0.0.1:8799/api/v1";
const STAR = 1000;

const oneDecimal = (value: number) =>
  value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const directoryRows = (page: Page, isMobile = false) =>
  isMobile
    ? page.getByRole("list", { name: /regular season/ }).getByRole("listitem")
    : page.locator("#directory-title").locator("xpath=ancestor::section").locator("tbody tr");

test.describe("player directory", () => {
  test("renders the first page on the server and paginates", async ({ page, isMobile }) => {
    await page.goto("/players");
    await expect(page.getByText("2099-00 regular season").first()).toBeVisible();
    await expect(directoryRows(page, isMobile)).toHaveCount(25);
    await expect(page.getByText("Page 1 of 2 · 30 total")).toBeVisible();
    await page.getByRole("link", { name: "Next page" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(directoryRows(page, isMobile)).toHaveCount(5);
  });

  test("sorting by a statistic orders every page on the server", async ({ page, request, isMobile }) => {
    test.skip(isMobile, "column headers are a desktop table feature");
    const top = await (await request.get(`${STUB}/players?season=2099-00&sort=-reb&limit=1`)).json();
    await page.goto("/players");
    await page.getByRole("link", { name: /^REB/ }).click();
    await expect(page).toHaveURL(/sort=-reb/);
    await expect(page.getByRole("columnheader", { name: /REB/ })).toHaveAttribute("aria-sort", "descending");
    await expect(directoryRows(page).first()).toContainText(top.items[0].full_name);
    await page.getByRole("link", { name: /^REB/ }).click();
    await expect(page).toHaveURL(/sort=reb/);
    await expect(page.getByRole("columnheader", { name: /REB/ })).toHaveAttribute("aria-sort", "ascending");
  });

  test("filters live in the URL and change the results", async ({ page, isMobile }) => {
    await page.goto("/players");
    await page.getByLabel("Team", { exact: true }).selectOption({ label: "Alpha Ants" });
    await expect(page).toHaveURL(/team=1/);
    await expect(directoryRows(page, isMobile)).toHaveCount(15);
    await page.getByRole("radio", { name: "Centers" }).click();
    await expect(page).toHaveURL(/position=C/);
    await expect(directoryRows(page, isMobile)).toHaveCount(6);
    await page.reload();
    await expect(page.getByRole("radio", { name: "Centers" })).toBeChecked();
    await expect(directoryRows(page, isMobile)).toHaveCount(6);

    await page.getByLabel("Season", { exact: true }).selectOption("2098-99");
    await expect(page).toHaveURL(/season=2098-99/);
    await expect(page.getByText("2098-99 regular season").first()).toBeVisible();

    await page.goto("/players");
    await page.getByLabel("Include former players").check();
    await expect(page).toHaveURL(/status=all/);
    await expect(page.getByText("Page 1 of 2 · 30 total")).toBeVisible();
  });

  test("shows an empty state with a way back", async ({ page, isMobile }) => {
    await page.goto("/players?team=99");
    await expect(page.getByText("No players match these filters")).toBeVisible();
    await page.getByRole("link", { name: "Clear filters" }).click();
    await expect(directoryRows(page, isMobile)).toHaveCount(25);
  });

  test("search opens a profile and focuses its heading", async ({ page, isMobile }) => {
    await page.goto("/players");
    await page.getByRole("combobox", { name: "Search players and teams" }).fill("zed");
    await page.getByRole("option", { name: /Zed Fixture/ }).click();
    await expect(page).toHaveURL(`/players/${STAR}`);
    const heading = page.getByRole("heading", { level: 1, name: "Zed Fixture" });
    await expect(heading).toBeVisible();
    if (!isMobile) await expect(heading).toBeFocused();
    await expect(page).toHaveTitle("Zed Fixture · Players · NBA Intelligence");
  });

  test("is accessible in both themes without overflow", async ({ page }) => {
    await page.goto("/players");
    await expectAccessible(page);
  });
});

test.describe("player profile", () => {
  test("shows exactly the statistics the API returns", async ({ page, request }) => {
    const stats = await (await request.get(`${STUB}/players/${STAR}/stats`)).json();
    const season = stats.seasons[0];
    await page.goto(`/players/${STAR}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Zed Fixture");
    await expect(page.getByText("Alpha Ants · G · 6′7″, 215 lb")).toBeVisible();
    const hero = page.getByRole("region", { name: "Zed Fixture" });
    await expect(hero.getByRole("link", { name: "Predict next game" })).toHaveAttribute("href", `/predict?player=${STAR}`);
    await expect(hero.getByRole("link", { name: "Compare" })).toHaveAttribute("href", `/compare?p1=${STAR}`);
    await expect(page.getByRole("heading", { name: `${season.season} regular season` })).toBeVisible();
    await expect(page.getByText(`${season.games_played} games played`)).toBeVisible();
    const averages = page.getByRole("region", { name: `${season.season} regular season` });
    for (const key of ["pts", "reb", "ast", "fg3m", "stl", "blk", "min"] as const) {
      const label = key === "fg3m" ? "3PM" : key.toUpperCase();
      const tile = averages
        .locator("div")
        .filter({ has: page.locator("dt", { hasText: new RegExp(`^${label}$`) }) });
      await expect(tile.locator("dd").first()).toHaveText(oneDecimal(season.per_game[key]));
    }
    const fg = averages.locator("div").filter({ has: page.locator("dt", { hasText: /^FG%$/ }) });
    await expect(fg.locator("dd").first()).toContainText(oneDecimal(season.shooting.fg_pct * 100));
  });

  test("stat and season selectors update the URL and the data", async ({ page }) => {
    await page.goto(`/players/${STAR}`);
    await page.getByRole("radio", { name: "REB" }).click();
    await expect(page).toHaveURL(/stat=reb/);
    await expect(page.getByRole("heading", { name: "Rebounds by game" })).toBeVisible();

    await page.getByRole("radio", { name: "Table", exact: true }).click();
    await expect(
      page.getByRole("region", { name: /Rebounds by game, 2099-00/ }).locator("tbody tr"),
    ).toHaveCount(30);

    await page.getByLabel("Season", { exact: true }).selectOption("2098-99");
    await expect(page).toHaveURL(/season=2098-99/);
    await expect(page.getByRole("heading", { name: "2098-99 regular season" })).toBeVisible();
    await expect(page.getByText("2 games played")).toBeVisible();
    await expect(page).toHaveURL(/stat=reb/);
  });

  test("splits open from the keyboard and the game log paginates", async ({ page, isMobile }) => {
    await page.goto(`/players/${STAR}`);
    // Streamed sections hydrate after load; a key press before then is lost.
    await page.waitForLoadState("networkidle");
    const splits = page.getByText("Home, away and rest splits");
    if (isMobile) await splits.click();
    else await splits.press("Enter");
    await expect(page.getByRole("region", { name: "Splits, 2099-00 regular season" })).toBeVisible();

    const log = page.getByRole("region", { name: "Game log, 2099-00, most recent first" });
    await expect(log.locator("tbody tr")).toHaveCount(20);
    await page
      .getByRole("navigation", { name: "Game log pages" })
      .getByRole("link", { name: "Next page" })
      .click();
    await expect(page).toHaveURL(/log=2/);
    await expect(log.locator("tbody tr")).toHaveCount(10);
  });

  test("a player without games explains why", async ({ page }) => {
    await page.goto("/players/1990");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Former Fixture");
    await expect(page.getByText("No game-by-game stats for this player")).toBeVisible();
  });

  test("a former player's career lists every season with career averages", async ({ page }) => {
    await page.goto("/players/1990");
    const hero = page.getByRole("definition").filter({ hasText: "15.5" });
    await expect(hero).toBeVisible();
    const career = page.getByRole("table", { name: "Former Fixture, career regular season averages by season" });
    await expect(career.locator("tbody tr")).toHaveCount(2);
    await expect(career.locator("tbody tr").first()).toContainText("2080-81");
    await expect(career.locator("tbody tr").nth(1)).toContainText("OLD");
    await expect(career.locator("tfoot")).toContainText("Career");
    await expect(career.locator("tfoot")).toContainText("145");
    await expect(page.getByText("Steals weren't tracked until 2081-82")).toBeVisible();
    await expectAccessible(page);
  });

  test("unknown players get a not-found page", async ({ page }) => {
    // The page streams, so the status line is sent before the lookup; the content is what matters.
    await page.goto("/players/424242");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Player not found");
    await expect(page.getByRole("link", { name: "Search players" })).toBeVisible();
  });

  test("an unavailable API shows a plain-language error", async ({ page }) => {
    await page.goto("/players/9503");
    const alert = page.getByRole("alert").filter({ hasText: "Something went wrong" });
    await expect(alert).toBeVisible();
    await expect(alert).not.toContainText("database_unavailable");
  });

  test("is accessible in both themes without overflow", async ({ page }) => {
    await page.goto(`/players/${STAR}`);
    await expectAccessible(page);
  });
});

test.describe("player chart time span", () => {
  test("switches between this season, each year and the career total", async ({ page }) => {
    await page.goto("/players/1000");
    const span = page.getByRole("radiogroup", { name: "Time span" });
    await span.getByRole("radio", { name: "By year" }).click();
    await expect(page).toHaveURL(/view=years/);
    await expect(page.getByRole("heading", { name: "Points by year" })).toBeVisible();
    await span.getByRole("radio", { name: "All time" }).click();
    await expect(page).toHaveURL(/view=all/);
    await expect(page.getByRole("heading", { name: "Points, all time" })).toBeVisible();
    await span.getByRole("radio", { name: "This season" }).click();
    await expect(page.getByRole("heading", { name: "Points by game" })).toBeVisible();
    await expect(page).not.toHaveURL(/view=/);
  });

  test("a former player opens on by-year, with no current-season option", async ({ page }) => {
    await page.goto("/players/1990");
    await expect(page.getByRole("heading", { name: "Points by year" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "This season" })).toHaveCount(0);
  });
});
