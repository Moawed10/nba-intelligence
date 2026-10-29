import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Synthetic API responses; the E2E suite never depends on a running backend or real data.
const RESULTS = [
  { id: 1, full_name: "Alpha Tester", position: "G", is_active: true, team_abbreviation: "AAA" },
  { id: 2, full_name: "Beta Tester", position: null, is_active: false, team_abbreviation: null },
];

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/players/search?**", (route) => route.fulfill({ json: RESULTS }));
  await page.goto("/players");
});

test("search lists players and stays accessible while open", async ({ page }) => {
  const input = page.getByRole("combobox", { name: "Search players" });
  await input.fill("tes");
  const listbox = page.getByRole("listbox", { name: "Matching players" });
  await expect(listbox.getByRole("option")).toHaveCount(2);
  await expect(input).toHaveAttribute("aria-expanded", "true");

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking.map((v) => v.id)).toEqual([]);

  const option = listbox.getByRole("option", { name: /Alpha Tester/ });
  const box = await option.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await option.click();
  await expect(page).toHaveURL("/players/1");
});

test("search is fully keyboard operable", async ({ page, isMobile }) => {
  test.skip(isMobile, "keyboard flow is covered on pointer devices");
  const input = page.getByRole("combobox", { name: "Search players" });
  await input.focus();
  await page.keyboard.type("tes");
  await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(2);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("option", { name: /Beta Tester/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/players/2");
});
