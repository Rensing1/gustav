import { expect, test, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherVisualSmokeUnit } from "./support/seed-data";

async function viewportTransform(page: Page): Promise<string> {
  return page.locator(".svelte-flow__viewport").evaluate((element) => getComputedStyle(element).transform);
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
  const beforeInitialPan = await viewportTransform(page);
  await dragPane(page);
  await expect.poll(() => viewportTransform(page)).not.toBe(beforeInitialPan);
  await page.getByRole("button", { name: "Fit View" }).click();

  const firstPhase = page.locator(".teacher-flow-phase-band__label").first();
  await firstPhase.click();
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toHaveCount(0);
  await firstPhase.click();
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toBeVisible();

  const freePoint = await freePanePoint(page);
  expect(freePoint).toBeTruthy();
  await page.mouse.click(freePoint!.x, freePoint!.y);
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toHaveCount(0);
  await firstPhase.click();
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toBeVisible();

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
  await expect(page.getByRole("complementary", { name: "Phase bearbeiten" })).toBeVisible();
  await expect(page.getByText(phaseTitle, { exact: true })).toBeVisible();

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
  await expect(page.getByText(moduleTitle, { exact: true })).toBeVisible();

  await modulePanel.getByRole("link", { name: "Inhalt bearbeiten" }).click();
  await expect(page).toHaveURL(/\/nodes\//);
  const editorPane = page.locator(".teacher-module-editor-pane");
  await expect(editorPane.getByRole("heading", { name: "Inhalt auswählen" })).toBeVisible();

  await page.getByRole("button", { name: "Material hinzufügen" }).first().click();
  await editorPane.getByLabel("Titel").fill("E2E Merkblatt");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await editorPane.getByRole("textbox", { name: "Inhalt" }).fill("Ein kurzer Materialtext.");
  await editorPane.getByRole("button", { name: "Material hinzufügen" }).click();
  await expect(page.getByText("Material angelegt.")).toBeVisible();

  await page.getByRole("button", { name: "Aufgabe hinzufügen" }).first().click();
  await editorPane.getByRole("textbox", { name: "Anweisung & Beschreibung" }).fill("Begründe deine Antwort.");
  await editorPane.getByRole("textbox", { name: "Kriterium 1", exact: true }).fill("Die Antwort ist nachvollziehbar begründet.");
  await editorPane.getByRole("button", { name: "Aufgabe hinzufügen" }).click();
  await expect(page.getByText("Aufgabe angelegt.")).toBeVisible();

  await page.getByRole("button", { name: /E2E Merkblatt/ }).click();
  await editorPane.getByLabel("Titel").fill("E2E Merkblatt Entwurf");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await editorPane.getByRole("textbox", { name: "Inhalt", exact: true }).fill("Geänderter Entwurfsinhalt.");
  await page.getByRole("button", { name: /Begründe deine Antwort/ }).click();
  await page.getByRole("button", { name: /E2E Merkblatt/ }).click();
  await expect(editorPane.getByLabel("Titel")).toHaveValue("E2E Merkblatt Entwurf");
  await expect(editorPane.getByRole("textbox", { name: "Inhalt", exact: true })).toContainText("Geänderter Entwurfsinhalt.");
  await page.reload();
  await expect(editorPane.getByLabel("Titel")).toHaveValue("E2E Merkblatt Entwurf");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await expect(editorPane.getByRole("textbox", { name: "Inhalt", exact: true })).toContainText("Geänderter Entwurfsinhalt.");
  await editorPane.getByRole("button", { name: "Verwerfen" }).click();
  await expect(editorPane.getByLabel("Titel")).toHaveValue("E2E Merkblatt");
  await expect(editorPane.getByRole("toolbar", { name: "Text formatieren" })).toBeVisible();
  await expect(editorPane.getByRole("textbox", { name: "Inhalt", exact: true })).toContainText("Ein kurzer Materialtext.");

  await editorPane.getByText("Aktionen").click();
  await editorPane.getByRole("button", { name: "Entfernen" }).click();
  const contentDeleteDialog = page.getByRole("dialog", { name: "Material löschen" });
  await expect(contentDeleteDialog).toContainText("E2E Merkblatt");
  await contentDeleteDialog.getByRole("button", { name: "Abbrechen" }).click();
  await editorPane.getByRole("button", { name: "Entfernen" }).click();
  await page.getByRole("dialog", { name: "Material löschen" }).getByRole("button", { name: "Material löschen" }).click();
  await expect(page.getByText("Material gelöscht.")).toBeVisible();

  await page.getByRole("link", { name: "Zurück zum Graph" }).click();
  await expect(page).toHaveURL(new RegExp(`/teaching/units/${unitId}\\?module=.*quick=1`));
  await expect(page.getByRole("complementary", { name: "Modul bearbeiten" })).toBeVisible();

  await page.getByRole("complementary", { name: "Modul bearbeiten" }).getByRole("button", { name: "Modul löschen" }).click();
  const moduleDeleteDialog = page.getByRole("dialog", { name: "Modul löschen" });
  await expect(moduleDeleteDialog).toContainText(moduleTitle);
  await expect(moduleDeleteDialog).toContainText("0 Materialien");
  await moduleDeleteDialog.getByRole("button", { name: "Abbrechen" }).click();
  await expect(moduleDeleteDialog).toHaveCount(0);

  await page.getByRole("complementary", { name: "Modul bearbeiten" }).getByRole("link", { name: "Inhalt bearbeiten" }).click();
  await page.getByLabel("Modulaktionen").click();
  await page.getByRole("button", { name: "Modul löschen" }).click();
  await page.getByRole("dialog", { name: "Modul löschen" }).getByRole("button", { name: "Modul und Inhalte löschen" }).click();
  await expect(page).toHaveURL(new RegExp(`/teaching/units/${unitId}(?:\\?.*)?$`));
  await expect(page.getByText(moduleTitle, { exact: true })).toHaveCount(0);

  const phasePanel = page.getByRole("complementary", { name: "Phase bearbeiten" });
  await expect(phasePanel.getByLabel("Name")).toHaveValue(phaseTitle);
  await phasePanel.getByRole("button", { name: "Phase löschen" }).click();
  const phaseDeleteDialog = page.getByRole("dialog", { name: "Phase löschen" });
  await expect(phaseDeleteDialog).toContainText(phaseTitle);
  await phaseDeleteDialog.getByRole("button", { name: "Phase und Inhalte löschen" }).click();
  await expect(page.getByText("Phase gelöscht.")).toBeVisible();
  await expect(page.getByText(phaseTitle, { exact: true })).toHaveCount(0);
});
