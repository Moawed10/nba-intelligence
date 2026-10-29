import { expect, type Page, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// Players 1000 ("Zed Fixture") and 1001 come from tests/e2e/stub-api.mjs; 1990 is a former player with no seasons.

async function pick(page: Page, slot: "Player 1" | "Player 2", query: string, name: string) {
  await page.getByRole("combobox", { name: slot }).fill(query);
  await page
    .getByRole("listbox")
    .getByRole("option", { name: new RegExp(name) })
    .click();
}

test.describe("compare", () => {
  test("builds a comparison from two searches and keeps it in the URL", async ({ page }) => {
    await page.goto("/compare");
    await expect(page.getByText("Pick two players")).toBeVisible();
    await pick(page, "Player 1", "zed", "Zed Fixture");
    await expect(page).toHaveURL(/\/compare\?p1=1000$/);
    await expect(page.getByText("Pick a second player")).toBeVisible();
    await pick(page, "Player 2", "player 01", "Test Player 01");
    await expect(page).toHaveURL(/p1=1000&p2=1001/);
    await expect(
      page.getByRole("region", { name: "Zed Fixture versus Test Player 01, 2099-00" }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Head to head" })).toContainText("Points");
  });

  test("swaps sides, changes season and removes a player", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1001");
    await page.getByRole("button", { name: "Swap players" }).click();
    await expect(page).toHaveURL(/p1=1001&p2=1000&season=2099-00/);
    await expect(page.getByRole("region", { name: /^Test Player 01 versus Zed Fixture/ })).toBeVisible();

    await page.getByRole("combobox", { name: "Season" }).selectOption("2098-99");
    await expect(page).toHaveURL(/season=2098-99/);
    await expect(page.getByRole("region", { name: /2098-99$/ })).toBeVisible();

    await page.getByRole("button", { name: "Remove Zed Fixture" }).click();
    await expect(page).toHaveURL(/\/compare\?p1=1001$/);
    await expect(page.getByText("Pick a second player")).toBeVisible();
  });

  test("refuses the same player twice", async ({ page }) => {
    await page.goto("/compare?p1=1000");
    await pick(page, "Player 2", "zed", "Zed Fixture");
    await expect(page.getByRole("status").filter({ hasText: "already in the other slot" })).toBeVisible();
    await expect(page).toHaveURL(/\/compare\?p1=1000$/);
  });

  test("explains players without a shared season and unknown ids", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1990");
    await expect(page.getByText("These players never played in the same season")).toBeVisible();
    await page.goto("/compare?p1=99999&p2=1000");
    await expect(page.getByText("A player in this link wasn't found")).toBeVisible();
    await expect(page.getByText("Pick a second player")).toBeVisible();
  });

  test("form chart switches statistic and has a table equivalent", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1001");
    const form = page.getByRole("region", { name: "Form" });
    await expect(
      form.getByText(/Zed Fixture averages [\d.]+ and Test Player 01 [\d.]+ points per game/),
    ).toBeVisible();
    await form.getByRole("radio", { name: "REB" }).click();
    await expect(form.getByText(/rebounds per game, over 30 and 30 games/)).toBeVisible();
    await form.getByRole("radio", { name: "Table" }).click();
    await expect(form.getByRole("table").getByRole("row")).toHaveCount(31);
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/compare?p1=1000&p2=1001");
    await expect(page.getByRole("region", { name: "Head to head" })).toBeVisible();
    await expectAccessible(page);
  });
});
