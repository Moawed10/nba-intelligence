/**
 * Phase 12 audit: every route and key state, against WCAG 2.2 AA (axe), keyboard operation,
 * visible focus, 200% zoom and 320 px reflow. Findings at every impact level are written to
 * test-results/a11y-audit/<project>-<worker>.json for docs/accessibility-report.md.
 */
import { mkdirSync, writeFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const PAGES = [
  { path: "/", name: "Overview" },
  { path: "/players", name: "Players directory" },
  { path: "/players/1000", name: "Player profile" },
  { path: "/players/1990", name: "Former player" },
  { path: "/predict", name: "Predictions (start)" },
  { path: "/predict?player=1000", name: "Predictions (forecast)" },
  { path: "/compare", name: "Compare (empty)" },
  { path: "/compare?p1=1000&p2=1001", name: "Compare (two players)" },
  { path: "/models", name: "Models" },
  { path: "/games?date=2099-11-09", name: "Games (final)" },
  { path: "/games?date=2099-11-10", name: "Games (upcoming)" },
  { path: "/games/0099000102", name: "Game page (upcoming)" },
  { path: "/games/0099000101", name: "Game page (final)" },
  { path: "/about", name: "About" },
  { path: "/teams/1", name: "Team" },
  { path: "/players/424242", name: "Not found" },
];

const results: Record<string, unknown>[] = [];

async function overflow(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test.afterAll(({}, info) => {
  mkdirSync("test-results/a11y-audit", { recursive: true });
  writeFileSync(
    `test-results/a11y-audit/${info.project.name}-${info.workerIndex}.json`,
    JSON.stringify(results, null, 2),
  );
});

for (const target of PAGES) {
  test(`axe WCAG 2.2 AA: ${target.name}`, async ({ page }, info) => {
    for (const theme of ["dark", "light"] as const) {
      await page.goto(target.path);
      await page.evaluate((t) => localStorage.setItem("nbai-theme", t), theme);
      await page.reload();
      await expect(page.locator("main h1")).toBeVisible();
      await page.waitForLoadState("networkidle");
      const axe = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      const violations = axe.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.length,
        targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")),
      }));
      results.push({ check: "axe", page: target.path, project: info.project.name, theme, violations });
      const blocking = violations.filter((v) => v.impact === "critical" || v.impact === "serious");
      expect(blocking, `${target.path} (${theme})`).toEqual([]);
    }
  });
}

for (const target of PAGES) {
  test(`keyboard: ${target.name} has visible focus and no trap`, async ({ page, isMobile }, info) => {
    test.skip(isMobile, "keyboard pass runs on desktop widths");
    await page.goto(target.path);
    await expect(page.locator("main h1")).toBeVisible();
    await page.waitForLoadState("networkidle");
    const seen: string[] = [];
    const invisible: string[] = [];
    let stuck = 0;
    for (let i = 0; i < 60; i++) {
      await page.keyboard.press("Tab");
      const focus = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) return null;
        const style = getComputedStyle(el);
        const visible =
          (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== "none";
        const label = el.getAttribute("aria-label") || el.textContent?.trim().slice(0, 40) || el.tagName;
        const path = [];
        for (let n: Element | null = el; n && n !== document.body; n = n.parentElement) {
          path.unshift(
            `${n.tagName}${n.id ? `#${n.id}` : ""}:${[...(n.parentElement?.children ?? [])].indexOf(n)}`,
          );
        }
        return { key: path.join(">"), label, visible };
      });
      if (!focus) continue;
      if (seen.at(-1) === focus.key) stuck += 1;
      else stuck = 0;
      expect(stuck, `focus stuck on ${focus.label}`).toBeLessThan(3);
      if (!focus.visible) invisible.push(focus.label);
      seen.push(focus.key);
    }
    const distinct = new Set(seen).size;
    results.push({
      check: "keyboard",
      page: target.path,
      project: info.project.name,
      stops: distinct,
      invisible,
    });
    expect(distinct, "focus reaches several controls").toBeGreaterThan(5);
    expect(invisible, "every focused element shows a focus indicator").toEqual([]);
  });
}

for (const target of PAGES) {
  test(`zoom and reflow: ${target.name}`, async ({ page, isMobile }, info) => {
    test.skip(isMobile, "viewport is set explicitly");
    // 200% zoom of a 1280 px window lays out like a 640 px viewport; 320 px is WCAG reflow.
    for (const width of [640, 320]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto(target.path);
      await expect(page.locator("main h1")).toBeVisible();
      await page.waitForLoadState("networkidle");
      const extra = await overflow(page);
      results.push({
        check: "reflow",
        page: target.path,
        project: info.project.name,
        width,
        overflow: extra,
      });
      expect(extra, `${target.path} at ${width}px`).toBeLessThanOrEqual(0);
    }
  });
}
