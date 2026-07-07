import { expect, type Locator, type Page } from "@playwright/test";

export type SmokePage = {
  path: string;
  heading: string;
};

export async function expectVisiblePageShell(page: Page, smokePage: SmokePage): Promise<void> {
  await page.goto(smokePage.path);
  await expect(page.getByRole("heading", { name: smokePage.heading })).toBeVisible();
  await expect(page.locator("body")).toContainText("GUSTAV");
  await expectInteractiveSurface(page.locator("body"));
  await expectNoViewportOverflow(page);
}

export async function expectInteractiveSurface(locator: Locator): Promise<void> {
  const metrics = await locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const visibleElements = [...element.querySelectorAll("a, button, input, form, main, section, [role='button']")]
      .filter((candidate) => {
        const rect = candidate.getBoundingClientRect();
        const styles = window.getComputedStyle(candidate);
        return rect.width > 0 && rect.height > 0 && styles.visibility !== "hidden" && styles.display !== "none";
      })
      .length;

    return {
      textLength: (element as HTMLElement).innerText.trim().length,
      width: box.width,
      height: box.height,
      visibleElements
    };
  });

  expect(metrics.textLength).toBeGreaterThan(20);
  expect(metrics.width).toBeGreaterThan(300);
  expect(metrics.height).toBeGreaterThan(200);
  expect(metrics.visibleElements).toBeGreaterThan(1);
}

export async function expectNoViewportOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return {
      horizontalOverflow: doc.scrollWidth - doc.clientWidth,
      bodyWidth: document.body.getBoundingClientRect().width,
      viewportWidth: window.innerWidth
    };
  });

  expect(overflow.horizontalOverflow).toBeLessThanOrEqual(4);
  expect(overflow.bodyWidth).toBeLessThanOrEqual(overflow.viewportWidth + 4);
}
