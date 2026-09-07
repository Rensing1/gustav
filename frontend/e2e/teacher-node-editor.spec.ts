import { expect, test } from "./support/feature-test";

import { apiHeaders, expectApiOk } from "./support/api";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherModuleEditorVisualUnit } from "./support/seed-data";

test("@feature-acceptance teacher edits linear and modular content and reopens persisted material", async ({ page }) => {
  const email = e2eEmail("teacher");
  await ensureTeacherUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  const unique = Date.now();
  const modular = await seedTeacherModuleEditorVisualUnit(page, `E2E Moduleditor ${unique}`);

  const unitResponse = await page.request.post(`${webBase}/api/teaching/units`, {
    headers: apiHeaders(), data: { title: `E2E Abschnittseditor ${unique}`, unit_type: "linear" }
  });
  await expectApiOk(unitResponse, 201);
  const unitId = (await unitResponse.json()).id as string;
  const sectionResponse = await page.request.post(`${webBase}/api/teaching/units/${unitId}/sections`, {
    headers: apiHeaders(), data: { title: "Quellen untersuchen" }
  });
  await expectApiOk(sectionResponse, 201);
  const sectionId = (await sectionResponse.json()).id as string;
  const materialResponse = await page.request.post(`${webBase}/api/teaching/units/${unitId}/sections/${sectionId}/materials`, {
    headers: apiHeaders(), data: { title: "Lineare Quelle", body_md: "Ein überprüfbarer Quellentext." }
  });
  await expectApiOk(materialResponse, 201);

  for (const entry of [
    { unit: unitId, node: sectionId, title: "Lineare Quelle", save: "Speichern" },
    { unit: modular.unitId, node: modular.moduleIds[0], title: "Argumentationshilfe", save: "Änderungen speichern" }
  ]) {
    const editorUrl = `/teaching/units/${entry.unit}/nodes/${entry.node}`;
    await page.goto(editorUrl);
    await page.getByRole("button", { name: new RegExp(entry.title) }).click();
    await expect(page.getByRole("heading", { name: "Material bearbeiten" })).toBeVisible();
    const updatedTitle = `${entry.title} überarbeitet ${unique}`;
    const materialForm = page.locator('form[action="?/saveMaterial"]');
    await materialForm.getByRole("textbox", { name: "Titel", exact: true }).fill(updatedTitle);
    const saved = page.waitForResponse((response) => response.request().method() === "POST" && response.url().includes("/nodes/") && response.url().includes("saveMaterial"));
    await materialForm.getByRole("button", { name: entry.save, exact: true }).click();
    expect((await saved).ok()).toBe(true);
    await expect(page.getByRole("button", { name: new RegExp(updatedTitle) })).toBeVisible();
    await page.goto("/teaching");
    await page.goto(editorUrl);
    await page.getByRole("button", { name: new RegExp(updatedTitle) }).click();
    await expect(materialForm.getByRole("textbox", { name: "Titel", exact: true })).toHaveValue(updatedTitle);
    await page.reload();
    await expect(page.getByRole("button", { name: new RegExp(updatedTitle) })).toBeVisible();
  }

  const outline = page.getByRole("complementary", { name: "Modulinhalte" });
  await outline.getByRole("button", { name: /Begründe deine Position/ }).click();
  await expect(page.getByRole("heading", { name: "Aufgabe bearbeiten" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Kriterium 1", exact: true })).toHaveValue("Die Position ist nachvollziehbar begründet.");
});
