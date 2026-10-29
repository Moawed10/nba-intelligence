import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const ROUTES = [
  { path: "/", title: "Overview" },
  { path: "/players", title: "Players" },
  { path: "/predict", title: "Predictions" },
  { path: "/compare", title: "Compare" },
  { path: "/models", title: "Models" },
  { path: "/games", title: "Games" },
  { path: "/about", title: "About" },
];
const PRIMARY = ROUTES.slice(0, 5);

async function horizontalOverflow(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

for (const route of ROUTES) {
  test(`${route.path} renders accessibly without overflow`, async ({ page }) => {
    const response = await page.goto(route.path);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(route.title);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page).toHaveTitle(route.path === "/" ? "NBA Intelligence" : `${route.title} · NBA Intelligence`);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    for (const theme of ["dark", "light"] as const) {
      // Switch themes the way a user does (stored choice + load) so no color transition is mid-flight.
      await page.evaluate((t) => localStorage.setItem("nbai-theme", t), theme);
      await page.reload();
      await expect(page.locator("html")).toHaveClass(theme === "dark" ? /dark/ : /^(?!.*dark)/);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
      expect(blocking.map((v) => `${theme}: ${v.id} — ${v.nodes.map((n) => n.target).join(", ")}`)).toEqual([]);
    }
  });
}

test("every primary destination is reachable from the navigation", async ({ page, isMobile }) => {
  await page.goto("/about");
  const nav = page.getByRole("navigation", { name: "Primary" }).locator("visible=true");
  for (const route of PRIMARY) {
    await nav.getByRole("link", { name: route.title, exact: true }).click();
    await expect(page).toHaveURL(route.path);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(route.title);
    await expect(nav.getByRole("link", { name: route.title, exact: true })).toHaveAttribute("aria-current", "page");
  }
  if (isMobile) {
    for (const link of await nav.getByRole("link").all()) {
      const box = await link.boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
      expect(box!.width).toBeGreaterThanOrEqual(44);
    }
  }
});

test("skip link is the first tab stop and moves focus to the content", async ({ page, isMobile }) => {
  test.skip(isMobile, "keyboard flow is covered on pointer devices");
  await page.goto("/players");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("More menu works with the keyboard and restores focus on Escape", async ({ page, isMobile }) => {
  test.skip(isMobile, "keyboard flow is covered on pointer devices");
  await page.goto("/");
  const trigger = page.getByRole("button", { name: "More destinations" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const menu = page.getByRole("menu");
  await expect(menu.getByRole("menuitem", { name: "Games" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(trigger).toBeFocused();

  // Opening with Enter focuses the first item (Games); one ArrowDown reaches About.
  await page.keyboard.press("Enter");
  await expect(menu.getByRole("menuitem", { name: "Games" })).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(menu.getByRole("menuitem", { name: "About" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/about");
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
});

test("theme choice applies immediately and survives a reload", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: /^Theme: Dark/ }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: /^Theme: Light/ })).toBeVisible();
});

test("content reflows at 320px without horizontal scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  for (const route of ROUTES) {
    await page.goto(route.path);
    expect(await horizontalOverflow(page), route.path).toBeLessThanOrEqual(0);
  }
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });
  test("transitions are effectively disabled", async ({ page }) => {
    await page.goto("/");
    const duration = await page
      .getByRole("button", { name: /^Theme:/ })
      .evaluate((el) => parseFloat(getComputedStyle(el).transitionDuration));
    expect(duration).toBeLessThan(0.001);
  });
});

test("top bar keeps spare room so font differences between systems cannot overflow it", async ({ page }) => {
  await page.goto("/about");
  const slack = await page.locator("header > div").evaluate((row) => {
    const children = [...row.children] as HTMLElement[];
    const used = children.reduce((sum, el) => sum + el.getBoundingClientRect().width, 0);
    const style = getComputedStyle(row);
    const gaps = parseFloat(style.columnGap || "0") * (children.length - 1);
    const padding = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
    return row.clientWidth - padding - gaps - used;
  });
  expect(slack).toBeGreaterThanOrEqual(24);
});
