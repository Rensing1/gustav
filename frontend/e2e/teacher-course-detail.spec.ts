import { newBrowserContext } from "./support/browser-context";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { addUnitToCourse, seedLearnerVisualSmokeCourse } from "./support/seed-data";
import { contrastRatio, expectNoViewportOverflow } from "./support/layout-sanity";

const password = e2ePassword;

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await newBrowserContext(browser, { baseURL: webBase });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance teacher manages a course in the flat detail workspace", async ({ browser }, testInfo) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, `E2E Kursdetail ${unique}`);
    const secondUnit = await addUnitToCourse(teacher.page, seeded.courseId, `Zweite Einheit ${unique}`);

    await teacher.page.goto("/teaching/courses");
    const catalogBox = await teacher.page.locator(".teacher-catalog").evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right };
    });

    await teacher.page.goto(`/teaching/courses/${seeded.courseId}`);
    const workspace = teacher.page.locator(".teacher-course-workspace");
    const workspaceBox = await workspace.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right };
    });
    expect(Math.abs(catalogBox.left - workspaceBox.left)).toBeLessThanOrEqual(1);
    expect(Math.abs(catalogBox.right - workspaceBox.right)).toBeLessThanOrEqual(1);
    await expect(teacher.page.getByRole("link", { name: "Lerneinheit hinzufügen" })).toHaveCount(1);
    await expect(teacher.page.getByText("Diagnostik öffnen")).toHaveCount(0);

    const originalFirstRow = teacher.page.locator(".teacher-course-unit-list__row").filter({ hasText: seeded.unitTitle });
    await originalFirstRow.locator("summary").click();
    await originalFirstRow.getByRole("button", { name: "Nach unten" }).click();
    await teacher.page.getByRole("button", { name: "Reihenfolge speichern" }).click();
    await teacher.page.reload();
    const reorderedRows = await teacher.page.locator(".teacher-course-unit-list__row").allTextContents();
    expect(reorderedRows[0]).toContain(secondUnit.unitTitle);

    await teacher.page.getByRole("button", { name: "Mitglieder verwalten" }).click();
    const membersDrawer = teacher.page.getByRole("dialog", { name: "Mitglieder verwalten" });
    await expect(membersDrawer).toBeVisible();
    const search = membersDrawer.getByRole("searchbox", { name: "Mitglieder durchsuchen" });
    expect((await search.boundingBox())!.height).toBeLessThanOrEqual(60);
    await teacher.page.keyboard.press("Escape");
    await expect(membersDrawer).toBeHidden();

    for (const theme of ["light", "dark"] as const) {
      const themeButton = teacher.page.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
      if (await themeButton.count()) await themeButton.click();
      for (const width of [1440, 1024, 390, 320]) {
        await teacher.page.setViewportSize({ width, height: 900 });
        await teacher.page.getByRole("button", { name: "Mitglieder verwalten" }).click();
        await search.fill("E2E");
        const palette = await search.evaluate((node) => ({ color: getComputedStyle(node).color, background: getComputedStyle(node).backgroundColor, height: node.getBoundingClientRect().height }));
        expect(palette.height).toBeGreaterThanOrEqual(44);
        expect(palette.height).toBeLessThanOrEqual(60);
        expect(contrastRatio(palette.color, palette.background)).toBeGreaterThanOrEqual(4.5);
        await expect(membersDrawer.getByRole("link", { name: "Profil", exact: true }).first()).toBeVisible();
        const memberRow = membersDrawer.getByRole("listitem").first();
        await expect(memberRow.getByRole("button", { name: "Entfernen", exact: true })).toBeHidden();
        await memberRow.locator("summary").filter({ hasText: "Weitere Aktionen" }).click();
        await memberRow.getByRole("button", { name: "Entfernen", exact: true }).click();
        await expect(memberRow.getByRole("button", { name: "Entfernen bestätigen", exact: true })).toBeVisible();
        await memberRow.getByRole("button", { name: "Abbrechen", exact: true }).click();
        await expect(memberRow.getByRole("link", { name: "Profil", exact: true })).toBeVisible();
        await expectNoViewportOverflow(teacher.page);
        await teacher.page.screenshot({ path: testInfo.outputPath(`members-${theme}-${width}.png`) });
        await teacher.page.keyboard.press("Escape");
        await expect(teacher.page.getByRole("button", { name: "Mitglieder verwalten" })).toBeFocused();
      }
    }
    await teacher.page.setViewportSize({ width: 1440, height: 900 });

    await teacher.page.getByRole("button", { name: "Mitglieder verwalten" }).click();
    const outsideSurface = teacher.page.getByRole("button", { name: "Seitenleiste schließen" });
    await outsideSurface.click({ position: { x: 100, y: 100 } });
    await expect(membersDrawer).toBeHidden();

    await teacher.page.getByRole("link", { name: "Kurs bearbeiten" }).click();
    await expect(teacher.page).toHaveURL(new RegExp(`/teaching/courses/${seeded.courseId}\\?course=1$`));
    let courseDrawer = teacher.page.getByRole("dialog", { name: "Kurs bearbeiten" });
    await expect(courseDrawer.getByRole("button", { name: "Kurs endgültig löschen" })).toBeHidden();
    await courseDrawer.locator("summary").filter({ hasText: "Weitere Aktionen" }).click();
    await expect(courseDrawer).toContainText("Mitgliedschaften");
    await expect(courseDrawer.getByRole("button", { name: "Kurs endgültig löschen" })).toBeVisible();
    await teacher.page.keyboard.press("Escape");
    await expect(courseDrawer).toBeHidden();
    await expect(teacher.page).toHaveURL(new RegExp(`/teaching/courses/${seeded.courseId}$`));

    await teacher.page.getByRole("link", { name: "Kurs bearbeiten" }).click();
    await expect(courseDrawer).toBeVisible();
    await teacher.page.keyboard.press("Escape");
    await expect(courseDrawer).toBeHidden();
    await expect(teacher.page).toHaveURL(new RegExp(`/teaching/courses/${seeded.courseId}$`));

    await teacher.page.reload();
    await expect(teacher.page.getByRole("dialog", { name: "Kurs bearbeiten" })).toHaveCount(0);

    await teacher.page.getByRole("link", { name: "Kurs bearbeiten" }).click();
    courseDrawer = teacher.page.getByRole("dialog", { name: "Kurs bearbeiten" });
    await courseDrawer.getByRole("button", { name: "Archivieren" }).click();
    await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toBeVisible();
    await expect(teacher.page.getByRole("button", { name: "Mitglieder ansehen" })).toBeVisible();
    await teacher.context.close();
    await learner.context.close();
});
