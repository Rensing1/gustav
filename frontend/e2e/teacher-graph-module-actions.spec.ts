import { expect, test, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherVisualSmokeUnit } from "./support/seed-data";

async function viewportTransform(page: Page): Promise<string> {
  return page.locator(".svelte-flow__viewport").evaluate((element) => getComputedStyle(element).transform);
}

async function graphWidth(page: Page): Promise<number> {
  return page.locator(".teacher-flow-workspace__canvas").evaluate((element) => element.getBoundingClientRect().width);
}

async function dragPane(page: Page): Promise<void> {
  const point = await freePanePoint(page);
  expect(point).toBeTruthy();
  const startX = point!.x;
  const startY = point!.y;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + 90, startY + 45, { steps: 8 });
  await page.mouse.up();
}

async function freePanePoint(page: Page): Promise<{ x: number; y: number } | null> {
  return page.locator(".svelte-flow__pane").first().evaluate((element) => {
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
}

test("@feature-acceptance phase and module workflows keep the graph context and confirm deletion", async ({ page }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const email = `e2e_teacher_graph_${unique}@${emailDomain}`;
  const password = "Passw0rd!e2e";
  await ensureTeacherUser(email, password);
  await login(page, email, password);

  const { unitId } = await seedTeacherVisualSmokeUnit(page, `E2E Graph ${unique}`);
  const phaseTitle = `E2E Phase ${Date.now()}`;
  const moduleTitle = `E2E Modul ${Date.now()}`;

  await page.goto(`/teaching/units/${unitId}`);
  await expect(page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Gesamtansicht" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Auswahl fokussieren" })).toBeVisible();
  const beforeInitialPan = await viewportTransform(page);
  await dragPane(page);
  await expect.poll(() => viewportTransform(page)).not.toBe(beforeInitialPan);
  await page.getByRole("button", { name: "Gesamtansicht" }).click();
  await page.waitForTimeout(250);

  const firstPhase = page.getByRole("link", { name: "PHASE 01 Phase 1" });
  await firstPhase.click();
  const phaseContext = page.getByRole("region", { name: "Ausgewählte Phase" });
  await expect(phaseContext).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toHaveCount(0);

  const existingModule = page.getByRole("link", {
    name: "Modul 01 Startmodul 0 Materialien · 0 Aufgaben"
  });
  await existingModule.click();
  const moduleContext = page.getByRole("region", { name: "Ausgewähltes Modul" });
  await expect(moduleContext).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toHaveCount(0);

  await page.goBack();
  await expect(phaseContext).toBeVisible();
  await page.goForward();
  await expect(moduleContext).toBeVisible();

  const widthBeforeInspector = await graphWidth(page);
  await moduleContext.getByRole("button", { name: "Eigenschaften" }).click();
  await expect(page.getByRole("complementary", { name: "Modul bearbeiten" })).toBeVisible();
  await expect.poll(() => graphWidth(page)).toBe(widthBeforeInspector);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("complementary", { name: "Modul bearbeiten" })).toHaveCount(0);
  await expect(moduleContext).toBeVisible();

  await page.getByRole("button", { name: "Lerneinheit bearbeiten" }).click();
  const unitDialog = page.getByRole("dialog", { name: "Lerneinheit bearbeiten" });
  await expect(unitDialog).toBeVisible();
  await page.reload();
  await expect(unitDialog).toBeVisible();
  await unitDialog.getByRole("button", { name: "Schließen" }).click();
  await expect(unitDialog).toHaveCount(0);
  await expect(page).not.toHaveURL(/edit=1/);

  for (const viewport of [
    { width: 1024, height: 768 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport);
    await expect(moduleContext).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await moduleContext.getByRole("button", { name: "Eigenschaften" }).click();
    const responsiveInspector = page.getByRole("complementary", { name: "Modul bearbeiten" });
    await expect(responsiveInspector).toBeVisible();
    if (viewport.width === 390) {
      await expect.poll(() => responsiveInspector.evaluate((element) => element.getBoundingClientRect().width)).toBe(390);
    }
    await page.keyboard.press("Escape");
    await expect(responsiveInspector).toHaveCount(0);
  }
  await page.setViewportSize({ width: 1440, height: 900 });

  const freePoint = await freePanePoint(page);
  expect(freePoint).toBeTruthy();
  await page.mouse.click(freePoint!.x, freePoint!.y);
  await expect(moduleContext).toHaveCount(0);
  await firstPhase.click();
  await expect(phaseContext).toBeVisible();

  const addPhaseButton = page.getByRole("button", { name: "Phase hinzufügen" });
  await addPhaseButton.click();
  const createPhasePanel = page.getByRole("complementary", { name: "Phase hinzufügen" });
  await expect(createPhasePanel).toBeVisible();
  await addPhaseButton.click();
  await expect(createPhasePanel).toHaveCount(0);
  await addPhaseButton.click();
  await expect(createPhasePanel).toBeVisible();
  await createPhasePanel.getByLabel("Titel").fill(phaseTitle);
  await createPhasePanel.getByRole("button", { name: "Phase anlegen" }).click();
  await expect(page.getByText("Phase angelegt.")).toBeVisible();
  const phasePanel = page.getByRole("complementary", { name: "Phase bearbeiten" });
  await expect(phasePanel).toBeVisible();
  await expect(phasePanel.getByLabel("Name")).toHaveValue(phaseTitle);

  await page.getByRole("toolbar", { name: "Graphwerkzeuge" }).getByRole("button", { name: "Modul hinzufügen" }).click();
  const createModulePanel = page.getByRole("complementary", { name: "Modul hinzufügen" });
  await expect(createModulePanel).toBeVisible();

  await createModulePanel.getByRole("button", { name: "Modul anlegen" }).click();
  await expect(page.getByText("Bitte gib Titel und Phase für das Modul an.")).toBeVisible();

  await createModulePanel.getByLabel("Titel").fill(moduleTitle);
  await expect(createModulePanel.getByLabel("Phase").locator("option:checked")).toHaveText(phaseTitle);

  await createModulePanel.getByRole("button", { name: "Modul anlegen" }).click();
  await expect(page.getByText("Modul angelegt.")).toBeVisible();
  const modulePanel = page.getByRole("complementary", { name: "Modul bearbeiten" });
  await expect(modulePanel).toBeVisible();
  await expect(modulePanel.getByLabel("Name")).toHaveValue(moduleTitle);

  await modulePanel.getByRole("link", { name: "Inhalt bearbeiten" }).click();
  await expect(page).toHaveURL(/\/nodes\//);
  const editorPane = page.locator(".teacher-module-editor-pane");
  await expect(editorPane.getByRole("heading", { name: "Inhalt auswählen" })).toBeVisible();

  await page.getByRole("button", { name: "Material hinzufügen" }).first().click();
  await editorPane.getByLabel("Titel").fill("E2E Merkblatt");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await editorPane.locator('[contenteditable="true"][aria-label="Inhalt"]').fill("Ein kurzer Materialtext.");
  await editorPane.getByRole("button", { name: "Material hinzufügen" }).click();
  await expect(page.getByText("Material angelegt.")).toBeVisible();

  await page.getByRole("button", { name: "Aufgabe hinzufügen" }).first().click();
  await editorPane.locator('[contenteditable="true"][aria-label="Anweisung & Beschreibung"]').fill("Begründe deine Antwort.");
  await editorPane.getByRole("textbox", { name: "Kriterium 1", exact: true }).fill("Die Antwort ist nachvollziehbar begründet.");
  await editorPane.getByRole("button", { name: "Aufgabe hinzufügen" }).click();
  await expect(page.getByText("Aufgabe angelegt.")).toBeVisible();

  await page.getByRole("button", { name: /E2E Merkblatt/ }).click();
  await editorPane.getByLabel("Titel").fill("E2E Merkblatt Entwurf");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await editorPane.locator('[contenteditable="true"][aria-label="Inhalt"]').fill("Geänderter Entwurfsinhalt.");
  await page.getByRole("button", { name: /Begründe deine Antwort/ }).click();
  await page.getByRole("button", { name: /E2E Merkblatt/ }).click();
  await expect(editorPane.getByLabel("Titel")).toHaveValue("E2E Merkblatt Entwurf");
  await expect(editorPane.locator('[contenteditable="true"][aria-label="Inhalt"]')).toContainText("Geänderter Entwurfsinhalt.");
  await page.reload();
  await expect(editorPane.getByLabel("Titel")).toHaveValue("E2E Merkblatt Entwurf");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await expect(editorPane.locator('[contenteditable="true"][aria-label="Inhalt"]')).toContainText("Geänderter Entwurfsinhalt.");
  await editorPane.getByRole("button", { name: "Verwerfen" }).click();
  await expect(editorPane.getByLabel("Titel")).toHaveValue("E2E Merkblatt");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await expect(editorPane.locator('[contenteditable="true"][aria-label="Inhalt"]')).toContainText("Ein kurzer Materialtext.");

  await editorPane.getByText("Aktionen").click();
  await editorPane.getByRole("button", { name: "Entfernen" }).click();
  const contentDeleteDialog = page.getByRole("dialog", { name: "Material löschen" });
  await expect(contentDeleteDialog).toContainText("E2E Merkblatt");
  await contentDeleteDialog.getByRole("button", { name: "Abbrechen" }).click();
  await editorPane.getByRole("button", { name: "Entfernen" }).click();
  await page.getByRole("dialog", { name: "Material löschen" }).getByRole("button", { name: "Material löschen" }).click();
  await expect(page.getByText("Material gelöscht.")).toBeVisible();

  await page.getByRole("link", { name: "Zurück zum Graph" }).click();
  await expect(page).toHaveURL(new RegExp(`/teaching/units/${unitId}\\?module=[^&]+$`));
  await expect(moduleContext).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Modul bearbeiten" })).toHaveCount(0);

  await moduleContext.getByLabel("Weitere Aktionen").click();
  await moduleContext.getByRole("button", { name: "Modul löschen" }).click();
  const moduleDeleteDialog = page.getByRole("dialog", { name: "Modul löschen" });
  await expect(moduleDeleteDialog).toContainText(moduleTitle);
  await expect(moduleDeleteDialog).toContainText("0 Materialien");
  await moduleDeleteDialog.getByRole("button", { name: "Abbrechen" }).click();
  await expect(moduleDeleteDialog).toHaveCount(0);

  await moduleContext.getByRole("link", { name: "Inhalt bearbeiten" }).click();
  await page.getByLabel("Modulaktionen").click();
  await page.getByRole("button", { name: "Modul löschen" }).click();
  await page.getByRole("dialog", { name: "Modul löschen" }).getByRole("button", { name: "Modul und Inhalte löschen" }).click();
  await expect(page).toHaveURL(new RegExp(`/teaching/units/${unitId}(?:\\?.*)?$`));
  await expect(page.getByText(moduleTitle, { exact: true })).toHaveCount(0);

  await expect(phaseContext).toContainText(phaseTitle);
  await phaseContext.getByLabel("Weitere Aktionen").click();
  await phaseContext.getByRole("button", { name: "Phase löschen" }).click();
  const phaseDeleteDialog = page.getByRole("dialog", { name: "Phase löschen" });
  await expect(phaseDeleteDialog).toContainText(phaseTitle);
  await phaseDeleteDialog.getByRole("button", { name: "Phase und Inhalte löschen" }).click();
  await expect(page.getByText("Phase gelöscht.")).toBeVisible();
  await expect(page.getByText(phaseTitle, { exact: true })).toHaveCount(0);
});
