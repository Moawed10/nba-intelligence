import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

// Server-rendered pages read from tests/e2e/stub-api.mjs (synthetic season 2099-00).
const STUB = "http://127.0.0.1:8799/api/v1";
const STAR = 1000;

const oneDecimal = (value: number) =>
  value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

async function expectAccessible(page: Page) {
  for (const theme of ["dark", "light"] as const) {
    await page.evaluate((t) => localStorage.setItem("nbai-theme", t), theme);
    await page.reload();
    await expect(page.locator("main h1")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking.map((v) => `${theme}: ${v.id} — ${v.nodes.map((n) => n.target).join(", ")}`)).toEqual([]);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  }
}

const directoryRows = (page: Page) => page.getByRole("region", { name: /players/i }).locator("tbody tr");

test.describe("player directory", () => {
  test("renders the first page on the server and paginates", async ({ page }) => {
    await page.goto("/players");
    await expect(directoryRows(page)).toHaveCount(25);
    await expect(page.getByText("Page 1 of 2 · 30 total")).toBeVisible();
    await page.getByRole("link", { name: "Next page" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(directoryRows(page)).toHaveCount(5);
  });

  test("filters live in the URL and change the results", async ({ page }) => {
    await page.goto("/players");
    await page.getByLabel("Team").selectOption({ label: "Alpha Ants" });
    await expect(page).toHaveURL(/team=1/);
    await expect(directoryRows(page)).toHaveCount(15);
    await page.getByLabel("Position").selectOption({ label: "Centers" });
    await expect(page).toHaveURL(/position=C/);
    await expect(directoryRows(page)).toHaveCount(6);
    await page.reload();
    await expect(page.getByLabel("Position")).toHaveValue("C");
    await expect(directoryRows(page)).toHaveCount(6);

    await page.goto("/players");
    await page.getByLabel("Include former players").check();
    await expect(page).toHaveURL(/status=all/);
    await expect(page.getByText("Page 1 of 2 · 31 total")).toBeVisible();
  });

  test("shows an empty state with a way back", async ({ page }) => {
    await page.goto("/players?team=99");
    await expect(page.getByText("No players match these filters")).toBeVisible();
    await page.getByRole("link", { name: "Clear filters" }).click();
    await expect(directoryRows(page)).toHaveCount(25);
  });

  test("search opens a profile and focuses its heading", async ({ page, isMobile }) => {
    await page.goto("/players");
    await page.getByRole("combobox", { name: "Search players" }).fill("zed");
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
    await expect(page.getByText("No regular-season games in our data")).toBeVisible();
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
