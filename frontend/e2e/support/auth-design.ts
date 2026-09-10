import { expect, type Page, type TestInfo } from "./feature-test";
import type { Locator } from "@playwright/test";
import { contrastRatio, expectNoViewportOverflow } from "./layout-sanity";

export async function authPictures(page: Page, testInfo: TestInfo, name: string, mask: Locator[] = []): Promise<void> {
  for (const theme of ["light", "dark"] as const) {
    const toggle = page.getByRole("button", { name: theme === "dark" ? "Dunkle Darstellung aktivieren" : "Helle Darstellung aktivieren" });
    if (await toggle.count()) await toggle.click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator(".kc-auth-card")).toHaveCount(1);
      await expect(page.locator(".kc-auth-card .kc-auth-card")).toHaveCount(0);
      await expectNoViewportOverflow(page);
      if (width < 720) await expect(page.locator(".kc-links > span:visible, .kc-locale-links > span:visible")).toHaveCount(0);
      for (const field of await page.locator('.kc-input, .kc-submit').all()) {
        const palette = await field.evaluate((node) => {
          const css = getComputedStyle(node);
          return { color: css.color, background: css.backgroundColor, height: node.getBoundingClientRect().height, boxSizing: css.boxSizing };
        });
        expect(palette.height).toBeGreaterThanOrEqual(44);
        expect(palette.boxSizing).toBe("border-box");
        expect(contrastRatio(palette.color, palette.background)).toBeGreaterThanOrEqual(4.5);
      }
      for (const text of await page.locator(".kc-links a, .kc-locale-links a, .kc-message, .kc-hint, #kc-theme-toggle").all()) {
        if (!(await text.isVisible())) continue;
        const palette = await text.evaluate((node) => {
          let surface: Element | null = node;
          while (surface && getComputedStyle(surface).backgroundColor === "rgba(0, 0, 0, 0)") surface = surface.parentElement;
          return { color: getComputedStyle(node).color, background: surface ? getComputedStyle(surface).backgroundColor : "rgb(255, 255, 255)" };
        });
        expect(contrastRatio(palette.color, palette.background)).toBeGreaterThanOrEqual(4.5);
      }
      for (const button of await page.locator(".kc-submit, #kc-theme-toggle").all()) {
        await button.hover();
        await button.focus();
        await page.keyboard.press("Tab");
        await page.keyboard.press("Shift+Tab");
        const palette = await button.evaluate((node) => ({ color: getComputedStyle(node).color, background: getComputedStyle(node).backgroundColor }));
        expect(contrastRatio(palette.color, palette.background)).toBeGreaterThanOrEqual(4.5);
        await expect(button).toBeFocused();
        await expect(button).not.toHaveCSS("outline-style", "none");
      }
      await page.screenshot({ path: testInfo.outputPath(`${name}-${theme}-${width}.png`), fullPage: true, mask });
    }
  }
}
