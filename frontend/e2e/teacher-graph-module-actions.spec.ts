import { expect, test, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherVisualSmokeUnit } from "./support/seed-data";

async function viewportTransform(page: Page): Promise<string> {
  return page.locator(".svelte-flow__viewport").evaluate((element) => getComputedStyle(element).transform);
}

async function dragPane(page: Page): Promise<void> {
  const pane = page.locator(".svelte-flow__pane").first();
  const point = await pane.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const xSteps = [0.15, 0.3, 0.5, 0.7, 0.85];
    const ySteps = [0.18, 0.32, 0.5, 0.68, 0.82];
    for (const yStep of ySteps) {
      for (const xStep of xSteps) {
        const x = box.left + box.width * xStep;
        const y = box.top + box.height * yStep;
        const top = document.elementFromPoint(x, y);
        if (
          top?.closest(".svelte-flow__pane")
          && !top.closest(".svelte-flow__node")
          && !top.closest(".svelte-flow__edge")
          && !top.closest(".svelte-flow__controls")
        ) {
          return { x, y };
        }
      }
    }
    return null;
  });
  expect(point).toBeTruthy();
  const startX = point!.x;
  const startY = point!.y;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + 90, startY + 45, { steps: 8 });
  await page.mouse.up();
}

test("@feature-acceptance module create and delete update the graph without a hard reload", async ({ page }) => {
  const unique = Date.now();
  const email = `e2e_teacher_graph_${unique}@${emailDomain}`;
  const password = "Passw0rd!e2e";
  await ensureTeacherUser(email, password);
  await login(page, email, password);

  const { unitId } = await seedTeacherVisualSmokeUnit(page, `E2E Graph ${unique}`);
  const moduleTitle = `E2E Modul ${Date.now()}`;

  await page.goto(`/teaching/units/${unitId}`);
  await expect(page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeVisible();
  const beforeInitialPan = await viewportTransform(page);
  await dragPane(page);
  await expect.poll(() => viewportTransform(page)).not.toBe(beforeInitialPan);
  await page.getByRole("button", { name: "Fit View" }).click();

  await page.getByRole("button", { name: "Modul hinzufügen" }).click();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toBeVisible();

  await page.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByText("Bitte gib Titel und Phase für das Modul an.")).toBeVisible();

  await page.getByLabel("Titel").fill(moduleTitle);

  const phaseSelect = page.getByLabel("Phase");
  if (!(await phaseSelect.inputValue())) {
    const firstPhaseValue = await phaseSelect.locator("option").nth(1).getAttribute("value");
    expect(firstPhaseValue).toBeTruthy();
    await phaseSelect.selectOption(firstPhaseValue!);
  }

  await page.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByText("Modul angelegt.")).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toHaveCount(0);
  await expect(page.getByText(moduleTitle, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Modul hinzufügen" }).click();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toBeVisible();
  await expect(page.getByText("Bitte gib Titel und Phase für das Modul an.")).toHaveCount(0);
  await page.getByRole("button", { name: "Schließen" }).click();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toHaveCount(0);

  const createdModule = page.locator(".teacher-flow-node--module").filter({ hasText: moduleTitle }).first();
  await createdModule.click();
  await expect(createdModule.getByRole("button", { name: "Eigenschaften" })).toBeVisible();
  await createdModule.getByRole("button", { name: "Eigenschaften" }).click();
  await expect(createdModule.getByRole("button", { name: "Modul löschen" })).toBeVisible();
  await createdModule.getByRole("button", { name: "Modul löschen" }).click();
  await expect(page.getByText("Modul gelöscht.")).toBeVisible();
  await expect(page.getByText(moduleTitle, { exact: true })).toHaveCount(0);

  const remainingModule = page.locator(".teacher-flow-node--module").first();
  if (await remainingModule.count()) {
    await remainingModule.click();
    await expect(page.getByRole("button", { name: "Eigenschaften" })).toBeVisible();
  }
});
