import { expect, test, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherVisualSmokeUnit } from "./support/seed-data";

type GraphGeometry = {
  canvas: { top: number; right: number; bottom: number; left: number; width: number; height: number };
  viewport: { width: number; height: number };
  modulesInsideCanvas: boolean;
  pageOverflowsHorizontally: boolean;
};

async function graphGeometry(page: Page): Promise<GraphGeometry> {
  return page.evaluate(() => {
    const canvas = document.querySelector<HTMLElement>(".teacher-flow-workspace__canvas")?.getBoundingClientRect();
    const modules = Array.from(document.querySelectorAll<HTMLElement>(".teacher-flow-node--module"));
    if (!canvas || modules.length === 0) throw new Error("graph_not_ready");
    return {
      canvas: {
        top: canvas.top,
        right: canvas.right,
        bottom: canvas.bottom,
        left: canvas.left,
        width: canvas.width,
        height: canvas.height
      },
      viewport: { width: innerWidth, height: innerHeight },
      modulesInsideCanvas: modules.every((module) => {
        const rect = module.getBoundingClientRect();
        return rect.left >= canvas.left - 1
          && rect.right <= canvas.right + 1
          && rect.top >= canvas.top - 1
          && rect.bottom <= canvas.bottom + 1;
      }),
      pageOverflowsHorizontally: document.documentElement.scrollWidth > innerWidth + 1
    };
  });
}

async function viewportTransform(page: Page): Promise<string> {
  return page.locator(".svelte-flow__viewport").evaluate((element) => getComputedStyle(element).transform);
}

async function waitForStableGraphLayout(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  });
}

async function waitForStableViewport(page: Page): Promise<void> {
  await page.locator(".svelte-flow__viewport").evaluate(async (element) => {
    let previous = "";
    let stableFrames = 0;
    for (let frame = 0; frame < 90; frame += 1) {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      const current = getComputedStyle(element).transform;
      stableFrames = current === previous ? stableFrames + 1 : 0;
      if (stableFrames >= 3) return;
      previous = current;
    }
    throw new Error("graph_viewport_did_not_settle");
  });
}

test("@feature-acceptance keeps the teacher module graph visible across iPad orientations", async ({ page }) => {
  test.setTimeout(90_000);
  const email = e2eEmail("teacher");
  await ensureTeacherUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  const seeded = await seedTeacherVisualSmokeUnit(page, `Graphfläche ${Date.now()}`);

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto(`/teaching/units/${seeded.unitId}`);
  await expect(page.locator(".teacher-flow-node--module")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
  await waitForStableGraphLayout(page);
  await waitForStableViewport(page);

  await expect.poll(() => graphGeometry(page)).toMatchObject({
    modulesInsideCanvas: true,
    pageOverflowsHorizontally: false
  });
  const landscape = await graphGeometry(page);
  expect(landscape.canvas.height / landscape.viewport.height).toBeGreaterThanOrEqual(0.6);

  const canvasHeightBeforeSelection = landscape.canvas.height;
  const phaseLink = page.getByRole("link", { name: "PHASE 01 Phase 1" });
  await expect(phaseLink).toBeInViewport();
  const phaseLinkBox = await phaseLink.boundingBox();
  if (!phaseLinkBox) throw new Error("phase_link_not_visible");
  await page.mouse.click(
    phaseLinkBox.x + phaseLinkBox.width / 2,
    phaseLinkBox.y + phaseLinkBox.height / 2
  );
  const context = page.getByRole("region", { name: "Ausgewählte Phase" });
  await expect(context).toBeVisible();
  await waitForStableGraphLayout(page);
  await waitForStableViewport(page);
  await expect.poll(async () => (await graphGeometry(page)).canvas.height).toBeCloseTo(canvasHeightBeforeSelection, 0);
  await expect.poll(async () => (await graphGeometry(page)).modulesInsideCanvas).toBe(true);

  const widthBeforeInspector = (await graphGeometry(page)).canvas.width;
  const cameraBeforeInspector = await viewportTransform(page);
  await context.getByRole("button", { name: "Eigenschaften" }).click();
  const inspector = page.getByRole("complementary", { name: "Phase bearbeiten" });
  await expect(inspector).toBeVisible();
  await expect.poll(async () => (await graphGeometry(page)).canvas.width).toBeCloseTo(widthBeforeInspector, 0);
  await expect.poll(() => viewportTransform(page)).toBe(cameraBeforeInspector);
  await page.keyboard.press("Escape");
  await expect(inspector).toHaveCount(0);
  await expect.poll(() => viewportTransform(page)).toBe(cameraBeforeInspector);

  await page.getByRole("button", { name: "Vergrößern", exact: true }).click();
  await waitForStableViewport(page);
  const storedCamera = await viewportTransform(page);
  expect(storedCamera).not.toBe(cameraBeforeInspector);
  await page.reload();
  await expect(page.locator(".teacher-flow-node--module")).toHaveCount(2);
  await waitForStableGraphLayout(page);
  await waitForStableViewport(page);
  await expect.poll(() => viewportTransform(page)).toBe(storedCamera);

  await page.setViewportSize({ width: 768, height: 1024 });
  await expect.poll(() => graphGeometry(page)).toMatchObject({
    modulesInsideCanvas: true,
    pageOverflowsHorizontally: false
  });
  await expect(page.getByRole("region", { name: "Ausgewählte Phase" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
});
