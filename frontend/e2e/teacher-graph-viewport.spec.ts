import { expect, test, type Page } from "./support/feature-test";

import { apiHeaders, expectApiOk } from "./support/api";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherVisualSmokeUnit } from "./support/seed-data";

type GraphGeometry = {
  canvas: { top: number; right: number; bottom: number; left: number; width: number; height: number };
  header: { height: number };
  graphToolsInsideCanvas: boolean;
  firstPhaseLabelInsideCanvas: boolean;
  phaseCount: number;
  secondPhaseLabelVisibleInCanvas: boolean;
  secondPhaseStartsInsideCanvas: boolean;
  viewport: { width: number; height: number };
  modulesInsideCanvas: boolean;
  pageOverflowsHorizontally: boolean;
};

async function graphGeometry(page: Page): Promise<GraphGeometry> {
  return page.evaluate(() => {
    const canvas = document.querySelector<HTMLElement>(".teacher-flow-workspace__canvas")?.getBoundingClientRect();
    const header = document.querySelector<HTMLElement>(".teacher-graph-workspace-frame .page-action-head")?.getBoundingClientRect();
    const graphTools = document.querySelector<HTMLElement>(".teacher-graph-workspace-frame__commandbar")?.getBoundingClientRect();
    const modules = Array.from(document.querySelectorAll<HTMLElement>(".teacher-flow-node--module"));
    const phases = Array.from(document.querySelectorAll<HTMLElement>(".teacher-flow-phase"))
      .map((phase) => phase.getBoundingClientRect())
      .sort((left, right) => left.top - right.top);
    const phaseLabels = Array.from(document.querySelectorAll<HTMLElement>(".teacher-flow-phase-band__label"))
      .map((label) => label.getBoundingClientRect())
      .sort((left, right) => left.top - right.top);
    if (
      !canvas || !header || !graphTools || modules.length === 0 || phases.length < 2 || phaseLabels.length < 2
    ) {
      throw new Error("graph_not_ready");
    }
    const firstPhaseLabel = phaseLabels[0];
    const secondPhase = phases[1];
    const secondPhaseLabel = phaseLabels[1];
    return {
      canvas: {
        top: canvas.top,
        right: canvas.right,
        bottom: canvas.bottom,
        left: canvas.left,
        width: canvas.width,
        height: canvas.height
      },
      header: { height: header.height },
      graphToolsInsideCanvas:
        graphTools.width > 0 &&
        graphTools.left >= canvas.left &&
        graphTools.top >= canvas.top &&
        graphTools.right <= canvas.right &&
        graphTools.bottom <= canvas.bottom,
      firstPhaseLabelInsideCanvas:
        firstPhaseLabel.left >= canvas.left - 1 &&
        firstPhaseLabel.right <= canvas.right + 1 &&
        firstPhaseLabel.top >= canvas.top - 1 &&
        firstPhaseLabel.bottom <= canvas.bottom + 1,
      phaseCount: phases.length,
      secondPhaseLabelVisibleInCanvas:
        secondPhaseLabel.left < canvas.right &&
        secondPhaseLabel.right > canvas.left &&
        secondPhaseLabel.top < canvas.bottom &&
        secondPhaseLabel.bottom > canvas.top,
      secondPhaseStartsInsideCanvas:
        secondPhase.left < canvas.right &&
        secondPhase.right > canvas.left &&
        secondPhase.top >= canvas.top - 1 &&
        secondPhase.top < canvas.bottom - 1,
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
  const secondPhaseResponse = await page.request.post(
    `${webBase}/api/teaching/units/${seeded.unitId}/phases`,
    {
      headers: apiHeaders(`/teaching/units/${seeded.unitId}`),
      data: { title: "Phase 2" }
    }
  );
  await expectApiOk(secondPhaseResponse, 201);

  // The scaled iPad Mini preview reports this effective CSS viewport.
  await page.setViewportSize({ width: 1137, height: 853 });
  await page.goto(`/teaching/units/${seeded.unitId}`);
  await expect(page.locator(".teacher-flow-node--module")).toHaveCount(2);
  await waitForStableGraphLayout(page);
  await waitForStableViewport(page);

  const scaledIpad = await graphGeometry(page);
  expect(scaledIpad.canvas.height / scaledIpad.viewport.height).toBeGreaterThanOrEqual(0.8);
  expect(scaledIpad.canvas.top / scaledIpad.viewport.height).toBeLessThanOrEqual(0.2);
  expect(scaledIpad.graphToolsInsideCanvas).toBe(true);
  expect(scaledIpad.header.height).toBeLessThan(90);
  expect(scaledIpad.phaseCount).toBe(2);
  expect(scaledIpad.firstPhaseLabelInsideCanvas).toBe(true);
  expect(scaledIpad.modulesInsideCanvas).toBe(true);
  expect(scaledIpad.secondPhaseLabelVisibleInCanvas).toBe(true);
  expect(scaledIpad.secondPhaseStartsInsideCanvas).toBe(true);
  await expect(page.locator(".workspace-unit-commandbar-heading")).toHaveCSS("position", "absolute");

  await page.setViewportSize({ width: 1024, height: 768 });
  await expect(page.locator(".teacher-flow-node--module")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
  await waitForStableGraphLayout(page);
  await waitForStableViewport(page);

  await expect.poll(() => graphGeometry(page)).toMatchObject({
    firstPhaseLabelInsideCanvas: true,
    modulesInsideCanvas: true,
    pageOverflowsHorizontally: false,
    secondPhaseLabelVisibleInCanvas: true,
    secondPhaseStartsInsideCanvas: true
  });
  const landscape = await graphGeometry(page);
  expect(landscape.canvas.height / landscape.viewport.height).toBeGreaterThanOrEqual(0.8);
  expect(landscape.canvas.top / landscape.viewport.height).toBeLessThanOrEqual(0.2);
  expect(landscape.graphToolsInsideCanvas).toBe(true);

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
  await expect(page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeHidden();
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

  await page.setViewportSize({ width: 911, height: 1311 });
  await waitForStableGraphLayout(page);
  await waitForStableViewport(page);
  await expect.poll(() => graphGeometry(page)).toMatchObject({
    modulesInsideCanvas: true,
    pageOverflowsHorizontally: false
  });
  await expect(page.locator(".workspace-unit-commandbar-heading")).toHaveCSS("position", "absolute");

  await page.setViewportSize({ width: 768, height: 1024 });
  await expect.poll(() => graphGeometry(page)).toMatchObject({
    modulesInsideCanvas: true,
    pageOverflowsHorizontally: false
  });
  await expect(page.getByRole("region", { name: "Ausgewählte Phase" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
});
