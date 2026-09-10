import { expect, test } from "./support/feature-test";
import { apiHeaders, expectApiOk } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureTeacherUser, ensureLearnerUser } from "./support/keycloak";
import { newBrowserContext } from "./support/browser-context";

test("@feature-acceptance linear sections separate selection and properties and preserve the return context", async ({ page, browser }, testInfo) => {
  const email = e2eEmail("teacher");
  await ensureTeacherUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  const created = await page.request.post(`${webBase}/api/teaching/units`, {
    headers: apiHeaders(), data: { title: `E2E Lineare Auswahl ${Date.now()}`, unit_type: "linear" }
  });
  await expectApiOk(created, 201);
  const unitId = (await created.json()).id as string;
  const sections: string[] = [];
  for (const title of ["Grundlagen", "Abschluss"]) {
    const response = await page.request.post(`${webBase}/api/teaching/units/${unitId}/sections`, {
      headers: apiHeaders(), data: { title }
    });
    await expectApiOk(response, 201);
    sections.push((await response.json()).id);
  }
  const graphUrl = `/teaching/units/${unitId}`;
  const bar = page.getByRole("region", { name: "Ausgewählter Abschnitt" });
  const inspector = page.getByRole("complementary", { name: "Abschnitt bearbeiten" });
  for (const [index, sectionId] of sections.entries()) {
    await page.goto(graphUrl);
    await page.getByRole("link", { name: new RegExp(index === 0 ? "Grundlagen" : "Abschluss") }).click();
    await expect(bar).toBeVisible();
    await expect(inspector).toHaveCount(0);
    await bar.getByRole("button", { name: "Eigenschaften" }).click();
    await expect(inspector).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(inspector).toHaveCount(0);
    await expect(bar.getByRole("button", { name: "Eigenschaften" })).toBeFocused();
    // A deliberate overview differs from the default readable focus.
    await page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
    const transform = await page.locator(".svelte-flow__viewport").getAttribute("style");
    await bar.getByRole("link", { name: "Inhalte bearbeiten" }).click();
    await expect(page).toHaveURL(new RegExp(`/nodes/${sectionId}$`));
    await page.getByRole("link", { name: "Zurück zum Graph" }).click();
    await expect(page).toHaveURL(new RegExp(`section=${sectionId}`));
    await expect(bar).toBeVisible();
    await expect(inspector).toHaveCount(0);
    await expect(page.locator(".svelte-flow__viewport")).toHaveAttribute("style", transform!);
  }
  // Old properties links remain usable, without becoming the default selection.
  await page.goto(`${graphUrl}?section=${sections[0]}&quick=1`);
  await expect(inspector).toBeVisible();
  await page.keyboard.press("Escape");
  for (const theme of ["light", "dark"]) {
    const themeButton = page.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
    if (await themeButton.count()) await themeButton.click();
    await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", theme);
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(bar).toBeVisible();
      await expect(page.locator(".svelte-flow__node")).toHaveCount(2);
      await page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
      await expect(page.getByRole("link", { name: /Grundlagen/ })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath(`linear-${theme}-${width}.png`), fullPage: true });
    }
  }
  for (const role of ["teacher", "student"] as const) {
    const otherEmail = e2eEmail(`${role}-outsider`);
    await (role === "teacher" ? ensureTeacherUser : ensureLearnerUser)(otherEmail, e2ePassword);
    const context = await newBrowserContext(browser);
    try {
      const other = await context.newPage();
      await login(other, otherEmail, e2ePassword);
      const response = await other.goto(`${graphUrl}/nodes/${sections[0]}`);
      if (role === "teacher") expect([403, 404]).toContain(response?.status());
      else await expect(other).not.toHaveURL(new RegExp(`/nodes/${sections[0]}`));
      const denied = await other.request.patch(`${webBase}/api/teaching/units/${unitId}/sections/${sections[0]}`, {
        headers: apiHeaders(), data: { title: "Unberechtigte Änderung" }
      });
      expect([403, 404]).toContain(denied.status());
      await expect(other.locator('form[action="?/saveMaterial"]')).toHaveCount(0);
      if (role === "student") {
        const courseResponse = await page.request.post(`${webBase}/api/teaching/courses`, {
          headers: apiHeaders(), data: { title: "E2E Abschnittstitel", subject: "Informatik", grade_level: "10", school_year_start: new Date().getFullYear() }
        });
        await expectApiOk(courseResponse, 201);
        const courseId = (await courseResponse.json()).id;
        const attached = await page.request.post(`${webBase}/api/teaching/courses/${courseId}/modules`, {
          headers: apiHeaders(), data: { unit_id: unitId }
        });
        await expectApiOk(attached, 201);
        const moduleId = (await attached.json()).id;
        const enrolled = await page.request.post(`${webBase}/api/teaching/courses/${courseId}/members`, {
          headers: apiHeaders(), data: { student_sub: await currentUserSub(other) }
        });
        expect([201, 204]).toContain(enrolled.status());
        for (const sectionId of sections) {
          await expectApiOk(await page.request.post(`${webBase}/api/teaching/units/${unitId}/sections/${sectionId}/materials`, {
            headers: apiHeaders(), data: { title: "Lesetext", body_md: "Inhalte zum Abschnitt." }
          }), 201);
          await expectApiOk(await page.request.patch(`${webBase}/api/teaching/courses/${courseId}/modules/${moduleId}/sections/${sectionId}/visibility`, {
            headers: apiHeaders(), data: { visible: true }
          }));
        }
        await other.goto(`/learning/courses/${courseId}/units/${unitId}`);
        await expect(other.getByText("Abschnitt 1 · Grundlagen", { exact: true }).first()).toBeVisible();
        await expect(other.getByText("Abschnitt 2 · Abschluss", { exact: true }).first()).toBeVisible();
        await other.screenshot({ path: testInfo.outputPath("learner-section-titles.png"), fullPage: true });
      }
    } finally {
      await context.close();
    }
  }
});
