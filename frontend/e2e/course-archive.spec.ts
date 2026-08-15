import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow, expectWorkspaceMeasure } from "./support/layout-sanity";
import { seedLearnerVisualSmokeCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true, acceptDownloads: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance teacher archives a course and learner exports only personal work", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_archive_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_archive_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, `E2E Archiv ${unique}`);

    await teacher.page.goto(`/teaching/courses/${seeded.courseId}?course=1`);
    const drawer = teacher.page.getByRole("dialog", { name: "Kurs bearbeiten" });
    await drawer.getByLabel("Fach").fill("Politik-Wirtschaft");
    await drawer.getByLabel("Jahrgang").fill("10");
    await drawer.getByRole("button", { name: "Speichern" }).click();
    await teacher.page.goto("/teaching/courses");
    const activeRow = teacher.page.locator(".workspace-course-catalog__row").filter({ hasText: seeded.courseTitle });
    await expect(activeRow).toContainText("Politik-Wirtschaft · 10");
    const courseCatalogBox = await teacher.page.locator(".teacher-catalog").evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right };
    });
    await teacher.page.goto("/teaching/units");
    await expect(teacher.page.getByRole("link", { name: seeded.unitTitle, exact: true })).toBeVisible();
    const unitCatalogBox = await teacher.page.locator(".teacher-catalog").evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right };
    });
    expect(Math.abs(courseCatalogBox.left - unitCatalogBox.left)).toBeLessThanOrEqual(1);
    expect(Math.abs(courseCatalogBox.right - unitCatalogBox.right)).toBeLessThanOrEqual(1);
    await teacher.page.goto("/teaching/courses");
    const refreshedActiveRow = teacher.page.locator(".workspace-course-catalog__row").filter({ hasText: seeded.courseTitle });
    await refreshedActiveRow.getByRole("checkbox").check();
    await teacher.page.getByRole("button", { name: "Archivieren" }).click();
    await teacher.page.goto("/teaching/courses?status=archived");
    await expect(teacher.page.getByRole("link", { name: seeded.courseTitle, exact: true })).toBeVisible();
    await teacher.page.getByRole("link", { name: seeded.courseTitle, exact: true }).click();
    await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toBeVisible();

    await learner.page.setViewportSize({ width: 1440, height: 900 });
    await learner.page.goto("/learning");
    await expectWorkspaceMeasure(learner.page, 1280);
    await expect(learner.page.getByRole("heading", { name: "Vergangene Kurse" })).toBeVisible();
    await learner.page.getByRole("link", { name: seeded.courseTitle }).click();
    await expectNoViewportOverflow(learner.page);
    await expectWorkspaceMeasure(learner.page, 1280);
    const portfolioGeometry = await learner.page.locator(".learning-portfolio").evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: window.innerWidth - box.right, width: box.width };
    });
    expect(Math.abs(portfolioGeometry.left - portfolioGeometry.right)).toBeLessThanOrEqual(2);
    expect(portfolioGeometry.width).toBeLessThanOrEqual(1026);
    await expect(learner.page.getByText("Meine frühere Einordnung bleibt als eigene Abgabe verfügbar.")).toBeVisible();
    await learner.page.getByRole("button", { name: "Lernleistung exportieren" }).click();
    await expect(learner.page.getByRole("status")).toContainText("Export wird erstellt");

    await expect.poll(async () => {
      const response = await learner.page.request.get(`${webBase}/api/learning/courses/${seeded.courseId}/portfolio`);
      if (!response.ok()) return "request-failed";
      return (await response.json()).latest_export?.status ?? "missing";
    }, { timeout: 45_000 }).toBe("ready");

    await learner.page.reload();
    const downloadPromise = learner.page.waitForEvent("download");
    await learner.page.getByRole("link", { name: "Fertiges Lernarchiv herunterladen" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^gustav-lernarchiv-.*\.zip$/);

    await teacher.page.goto(`/teaching/courses/${seeded.courseId}?course=1`);
    await teacher.page.getByRole("button", { name: "Wiederherstellen" }).click();
    await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toHaveCount(0);
    await teacher.page.goto(`/teaching/courses/${seeded.courseId}?course=1`);
    await teacher.page.getByRole("button", { name: "Archivieren" }).click();
    await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toBeVisible();
  } finally {
    await teacher.context.close();
    await learner.context.close();
  }
});

test("@feature-acceptance teacher permanently deletes only an isolated test course after strong confirmation", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_delete_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_delete_${unique}@${emailDomain}`;
  const foreignTeacherEmail = `e2e_teacher_delete_foreign_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  await ensureTeacherUser(foreignTeacherEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  const foreignTeacher = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    await login(foreignTeacher.page, foreignTeacherEmail, password);
    const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, `E2E Löschen ${unique}`);

    await teacher.page.goto(`/teaching/courses/${seeded.courseId}?course=1`);
    const drawer = teacher.page.getByRole("dialog", { name: "Kurs bearbeiten" });
    await drawer.getByLabel("Bestätigung").fill("falscher Titel");
    await drawer.getByLabel(/unwiderruflichen Verlust/).check();
    await drawer.getByRole("button", { name: "Kurs endgültig löschen" }).click();
    await expect(drawer.getByText("Bitte gib den Kurstitel exakt")).toBeVisible();

    await drawer.getByLabel("Bestätigung").fill(seeded.courseTitle);
    await drawer.getByLabel(/unwiderruflichen Verlust/).check();
    await drawer.getByRole("button", { name: "Kurs endgültig löschen" }).click();
    await expect(teacher.page).toHaveURL(/\/teaching\/courses$/);
    await expect(teacher.page.getByText(seeded.courseTitle, { exact: true })).toHaveCount(0);

    const deletionJobsResponse = await teacher.page.request.get(
      `${webBase}/api/teaching/course-deletion-jobs?include_completed=true`,
    );
    expect(deletionJobsResponse.ok()).toBeTruthy();
    const deletionJob = (await deletionJobsResponse.json() as Array<{
      id: string;
      course_id: string;
      status: string;
    }>).find((job) => job.course_id === seeded.courseId);
    expect(deletionJob?.id).toBeTruthy();

    await expect.poll(async () => {
      const response = await teacher.page.request.get(
        `${webBase}/api/teaching/course-deletion-jobs/${deletionJob!.id}`,
      );
      if (!response.ok()) return `http-${response.status()}`;
      return (await response.json()).status;
    }, { timeout: 45_000 }).toBe("completed");

    const repeatedJob = await teacher.page.evaluate(async ({ courseId, courseTitle }) => {
      const response = await fetch(`/api/teaching/courses/${courseId}/deletion-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmation_title: courseTitle,
          confirm_student_data_loss: true,
        }),
      });
      return { status: response.status, body: await response.json() };
    }, { courseId: seeded.courseId, courseTitle: seeded.courseTitle });
    expect(repeatedJob.status).toBe(202);
    expect(repeatedJob.body.id).toBe(deletionJob!.id);
    expect(repeatedJob.body.status).toBe("completed");

    const foreignRead = await foreignTeacher.page.request.get(
      `${webBase}/api/teaching/course-deletion-jobs/${deletionJob!.id}`,
    );
    expect(foreignRead.status()).toBe(404);

    await learner.page.goto("/learning");
    await expect(learner.page.getByRole("link", { name: seeded.courseTitle })).toHaveCount(0);
  } finally {
    await teacher.context.close();
    await learner.context.close();
    await foreignTeacher.context.close();
  }
});
