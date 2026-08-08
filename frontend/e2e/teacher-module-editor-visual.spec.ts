import { expect, test, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherModuleEditorVisualUnit } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function waitForStablePage(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

test.describe("@visual-smoke @design-system module editor workspace", () => {
  for (const viewport of [
    { name: "desktop", width: 1920, height: 1080 },
    { name: "tablet", width: 1024, height: 768 },
    { name: "mobile", width: 390, height: 844 }
  ] as const) {
    test(`keeps the flat content workspace on ${viewport.name}`, async ({ page }) => {
      const email = `visual_module_editor_${viewport.name}@${emailDomain}`;
      await ensureTeacherUser(email, password);
      await page.setViewportSize(viewport);
      await login(page, email, password);
      const seeded = await seedTeacherModuleEditorVisualUnit(page, "Lernstandserhebung");
      const moduleId = seeded.moduleIds[0];

      await page.goto(`/teaching/units/${seeded.unitId}/nodes/${moduleId}`);
      await waitForStablePage(page);

      const workbench = page.locator(".teacher-module-workbench");
      const outline = page.getByRole("complementary", { name: "Modulinhalte" });
      const editor = page.locator(".teacher-module-editor-pane");
      await expect(outline).toBeVisible();
      if (viewport.width >= 1280) {
        await expect(page.getByRole("heading", { name: "Inhalt auswählen" })).toBeVisible();
        await expect(editor).toBeVisible();
        const columns = await workbench.evaluate((element) => getComputedStyle(element).gridTemplateColumns);
        expect(columns.split(" ")).toHaveLength(2);
      } else {
        await expect(editor).toBeHidden();
      }

      await expect(page).toHaveScreenshot(`teacher-module-editor-light-${viewport.name}-overview.png`, {
        animations: "disabled",
        caret: "hide"
      });

      await outline.getByRole("button", { name: /Argumentationshilfe/ }).click();
      await expect(editor.getByRole("heading", { name: "Material bearbeiten" })).toBeVisible();
      await expect(editor.getByRole("textbox", { name: "Inhalt" })).toBeVisible();
      await waitForStablePage(page);
      await expect(page).toHaveScreenshot(`teacher-module-editor-light-${viewport.name}-material.png`, {
        animations: "disabled",
        caret: "hide"
      });

      await page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await expect(page).toHaveScreenshot(`teacher-module-editor-dark-${viewport.name}-material.png`, {
        animations: "disabled",
        caret: "hide"
      });
    });
  }
});
