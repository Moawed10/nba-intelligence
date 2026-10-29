import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/** Axe (WCAG 2.2 AA, serious and critical) and horizontal overflow, in both themes. */
export async function expectAccessible(page: Page) {
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
