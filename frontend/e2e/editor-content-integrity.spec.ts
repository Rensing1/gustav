import { expect, test } from "./support/feature-test";
import { apiHeaders, expectApiOk } from "./support/api";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherModuleEditorVisualUnit } from "./support/seed-data";

test("@feature-acceptance existing inline code survives an unchanged editor save and reload", async ({ page }, testInfo) => {
  const email = e2eEmail("teacher");
  await ensureTeacherUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  const unit = await seedTeacherModuleEditorVisualUnit(page, `E2E Inhaltserhalt ${Date.now()}`);
  const body = 'Dateien: `.sb3`, `.hex` und `.fls`.\n\n```js\n<script>alert(1)</script>\n```';
  // Seed through the real contract; only saving and reopening use the editor.
  const response = await page.request.patch(`${webBase}/api/teaching/units/${unit.unitId}/modules/${unit.moduleIds[0]}/materials/${unit.materialId}`, {
    headers: apiHeaders(), data: { body_md: body }
  });
  await expectApiOk(response);
  const editorUrl = `/teaching/units/${unit.unitId}/nodes/${unit.moduleIds[0]}`;
  await page.goto(editorUrl);
  await page.getByRole("button", { name: /Argumentationshilfe/ }).click();
  const form = page.locator('form[action="?/saveMaterial"]');
  const content = form.locator('[contenteditable="true"]');
  await expect(content).toContainText(".sb3");
  const saved = page.waitForResponse((r) => r.request().method() === "POST" && r.url().includes("saveMaterial"));
  await form.getByRole("button", { name: "Änderungen speichern", exact: true }).click();
  expect((await saved).ok()).toBe(true);
  await page.goto("/teaching");
  await page.goto(editorUrl);
  await page.getByRole("button", { name: /Argumentationshilfe/ }).click();
  await expect(form.locator('input[name="body_md"]')).toHaveValue(body);
  await expect(content.locator("script")).toHaveCount(0);
  for (const theme of ["light", "dark"]) {
    const themeButton = page.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
    if (await themeButton.count()) await themeButton.click();
    await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", theme);
    // Capture the settled theme rather than an intermediate color transition.
    await page.waitForTimeout(250);
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(content).toContainText(".hex");
      await expect(content).toContainText(".fls");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`editor-${theme}-${width}.png`), fullPage: true });
    }
  }
});
