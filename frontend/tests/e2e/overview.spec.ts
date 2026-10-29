import { expect, test } from "@playwright/test";

import { expectAccessible } from "./helpers";

// Overview reads tests/e2e/stub-api.mjs: "today" is 2099-11-10 with one scheduled game, one final the day before.

test.describe("overview", () => {
  test("opens on today's games and browses other days", async ({ page }) => {
    await page.goto("/");
    const schedule = page.getByRole("region", { name: "Games" });
    await expect(schedule.getByText("Nov 10, 2099", { exact: true })).toBeVisible();
    await expect(schedule.getByRole("button", { name: /Bravo at Alpha/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(schedule.getByText("Bravo Bears")).toBeVisible();
    await expect(schedule.getByText("6–4")).toBeVisible();

    await schedule.getByRole("button", { name: "Previous day" }).click();
    await expect(schedule.getByText("Nov 9, 2099", { exact: true })).toBeVisible();
    await expect(schedule.getByRole("button", { name: /Alpha at Bravo, Final/ })).toBeVisible();
    await expect(schedule.getByText("AAA top scorer")).toBeVisible();

    await schedule.getByRole("button", { name: "Previous day" }).click();
    await expect(schedule.getByText("No games on Nov 8, 2099")).toBeVisible();
  });

  test("switches leader categories without leaving the page", async ({ page }) => {
    await page.goto("/");
    const leaders = page.getByRole("region", { name: "League leaders" });
    await expect(
      leaders.getByRole("list", { name: "Points per game leaders" }).getByRole("listitem"),
    ).toHaveCount(5);
    await leaders.getByRole("radio", { name: "AST" }).click();
    await expect(leaders.getByRole("list", { name: "Assists per game leaders" })).toBeVisible();
    await expect(leaders.getByText(/Assists per game, 2099-00 regular season/)).toBeVisible();
    await expect(page).toHaveURL("/");
  });

  test("shows standouts, model accuracy and freshness from the API", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("region", { name: "Standout performances" }).getByRole("listitem"),
    ).toHaveCount(3);
    const model = page.getByRole("region", { name: "Model accuracy" });
    await expect(model.getByText("Serving predictions")).toBeVisible();
    await expect(model.getByRole("row", { name: /Points 4\.50 4\.70 80%/ })).toBeVisible();
    await expect(model.getByRole("link", { name: "Full evaluation" })).toHaveAttribute("href", "/models");
    await expect(page.getByRole("region", { name: "Freshness" }).getByRole("listitem")).toHaveCount(3);
  });

  test("is accessible in both themes without horizontal overflow", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("region", { name: "League leaders" }).getByRole("listitem").first(),
    ).toBeVisible();
    await expectAccessible(page);
  });
});
