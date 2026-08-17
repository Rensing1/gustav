import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { currentUserSub, login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";
import { prepareCompletedFeedbackDraft } from "./support/submission-finalization-fixture";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance finalizes a reviewed task with immediate visible progress", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `task_final_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `task_final_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Endgültige Abgabe ${unique}`);
    const reviewedText = "Diese geprüfte Fassung wird endgültig abgegeben.";
    await prepareCompletedFeedbackDraft({
      courseId: seeded.courseId,
      taskId: seeded.taskId,
      learnerSub,
      textBody: reviewedText
    });

    const draftKey = `gustav.learning.submission-draft:${encodeURIComponent(learnerSub)}:${seeded.courseId}:${seeded.taskId}:text`;
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.evaluate(({ key, value }) => window.sessionStorage.setItem(key, value), {
      key: draftKey,
      value: reviewedText
    });
    await learner.page.goto(
      `/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}&panel=result`
    );

    const editor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    const finalButton = learner.page.getByRole("button", { name: "Endgültig abgeben" });
    await expect(editor).toContainText(reviewedText);
    await expect(finalButton).toBeEnabled();

    let finalizationRequests = 0;
    await learner.page.route(`**/learning/courses/${seeded.courseId}/units/${seeded.unitId}**`, async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      finalizationRequests += 1;
      await new Promise((resolve) => setTimeout(resolve, 600));
      await route.continue();
    });

    await finalButton.evaluate((button: HTMLButtonElement) => {
      button.click();
      button.click();
    });

    const status = learner.page.locator(".learning-task-feedback-status").getByRole("status");
    await expect(status).toContainText("Abgabe wird verarbeitet ...");
    await expect(finalButton).toBeDisabled();
    await expect(learner.page.getByRole("button", { name: "Rückmeldung erneut einholen" })).toBeDisabled();
    await expect(status).toContainText("Aufgabe abgegeben");
    expect(finalizationRequests).toBe(1);
    await expect.poll(() => learner.page.evaluate((key) => window.sessionStorage.getItem(key), draftKey)).toBeNull();

    await learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" }).click();
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await expect(learner.page.getByRole("button", { name: "Erneut bearbeiten" })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});

test("@feature-acceptance finalizes the reviewed uploaded file", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `task_file_final_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `task_file_final_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Endgültige Datei-Abgabe ${unique}`);
    await prepareCompletedFeedbackDraft({
      courseId: seeded.courseId,
      taskId: seeded.taskId,
      learnerSub,
      kind: "file"
    });

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.goto(
      `/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}&panel=result`
    );

    const finalButton = learner.page.getByRole("button", { name: "Endgültig abgeben" });
    await expect(learner.page.getByRole("region", { name: "Bisherige Datei" })).toContainText("Aktuelle Datei");
    await expect(finalButton).toBeEnabled();
    await finalButton.click();

    const status = learner.page.locator(".learning-task-feedback-status").getByRole("status");
    await expect(status).toContainText("Abgabe wird verarbeitet ...");
    await expect(status).toContainText("Aufgabe abgegeben");

    const historyResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions?limit=10&offset=0`
    );
    expect(historyResponse.ok(), await historyResponse.text()).toBe(true);
    const history = await historyResponse.json() as Array<{ intent: string; kind: string }>;
    expect(history[0]).toMatchObject({ intent: "submit", kind: "file" });
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
