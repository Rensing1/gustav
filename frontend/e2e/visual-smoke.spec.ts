import { expect, test, type Page } from "@playwright/test";


type SmokePage = {
  path: string;
  heading: string;
};


const smokePages: SmokePage[] = [
  { path: "/", heading: "Anmelden" },
  { path: "/register", heading: "Registrieren" },
  { path: "/forgot-password", heading: "Passwort zurücksetzen" }
];


async function expectVisiblePageShell(page: Page, smokePage: SmokePage): Promise<void> {
  await page.goto(smokePage.path);
  await expect(page.getByRole("heading", { name: smokePage.heading })).toBeVisible();
  await expect(page.locator("body")).toContainText("GUSTAV");

  const metrics = await page.evaluate(() => {
    const body = document.body;
    const box = body.getBoundingClientRect();
    const visibleElements = [...document.querySelectorAll("a, button, input, form, main, section")]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        const styles = window.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && styles.visibility !== "hidden" && styles.display !== "none";
      })
      .length;

    return {
      textLength: body.innerText.trim().length,
      width: box.width,
      height: box.height,
      visibleElements
    };
  });

  expect(metrics.textLength).toBeGreaterThan(20);
  expect(metrics.width).toBeGreaterThan(300);
  expect(metrics.height).toBeGreaterThan(300);
  expect(metrics.visibleElements).toBeGreaterThan(3);
}


test.describe("@visual-smoke auth shell pages", () => {
  for (const viewport of [
    { name: "desktop", width: 1280, height: 900 },
    { name: "mobile", width: 390, height: 844 }
  ]) {
    test(`render non-empty auth shells on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      for (const smokePage of smokePages) {
        await expectVisiblePageShell(page, smokePage);
      }
    });
  }
});
