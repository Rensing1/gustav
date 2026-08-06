import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerVisualSmokeCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true, acceptDownloads: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance teacher archives a course and learner exports only personal work", async ({ browser }) => {
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
    await activeRow.getByRole("checkbox").check();
    await teacher.page.getByRole("button", { name: "Archivieren" }).click();
    await teacher.page.goto("/teaching/courses?status=archived");
    await expect(teacher.page.getByRole("link", { name: seeded.courseTitle, exact: true })).toBeVisible();
    await teacher.page.getByRole("link", { name: seeded.courseTitle, exact: true }).click();
    await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toBeVisible();

    await learner.page.goto("/learning");
    await expect(learner.page.getByRole("heading", { name: "Vergangene Kurse" })).toBeVisible();
    await learner.page.getByRole("link", { name: seeded.courseTitle }).click();
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
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_delete_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_delete_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
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

    await expect.poll(async () => {
      const response = await teacher.page.request.get(`${webBase}/api/teaching/courses/${seeded.courseId}`);
      return [403, 404].includes(response.status()) ? "inaccessible" : response.status();
    }, { timeout: 15_000 }).toBe("inaccessible");

    await learner.page.goto("/learning");
    await expect(learner.page.getByRole("link", { name: seeded.courseTitle })).toHaveCount(0);
  } finally {
    await teacher.context.close();
    await learner.context.close();
  }
});
