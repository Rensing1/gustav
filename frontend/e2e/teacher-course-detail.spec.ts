import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { addUnitToCourse, seedLearnerVisualSmokeCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance teacher manages a course in the flat detail workspace", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_course_detail_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_course_detail_${unique}@${emailDomain}`;
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
    await membersDrawer.getByRole("button", { name: "Schließen" }).click();

    await teacher.page.getByRole("link", { name: "Kurs bearbeiten" }).click();
    await expect(teacher.page).toHaveURL(new RegExp(`/teaching/courses/${seeded.courseId}\\?course=1$`));
    const courseDrawer = teacher.page.getByRole("dialog", { name: "Kurs bearbeiten" });
    await expect(courseDrawer).toContainText("Mitgliedschaften");
    await courseDrawer.getByRole("button", { name: "Archivieren" }).click();
    await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toBeVisible();
    await expect(teacher.page.getByRole("button", { name: "Mitglieder ansehen" })).toBeVisible();
    await teacher.context.close();
    await learner.context.close();
});
