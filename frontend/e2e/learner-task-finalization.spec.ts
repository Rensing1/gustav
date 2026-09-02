import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";
import {
  completeQueuedFeedbackDeterministically,
  holdProviderWorker,
  prepareCompletedFeedbackDraft,
  releaseProviderWorker
} from "./support/submission-finalization-fixture";

const password = e2ePassword;

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance finalizes a reviewed task with immediate visible progress", async ({ browser }) => {
  test.setTimeout(120_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
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
    await learner.page.goto(`/learning/courses/${seeded.courseId}`);
    await learner.page.getByRole("link", { name: seeded.unitTitle }).click();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();

    const editor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await editor.fill(reviewedText);

    await holdProviderWorker();
    try {
      await learner.page.getByRole("button", { name: "Rückmeldung einholen" }).click();
      await expect(
        learner.page
          .locator(".learning-task-feedback-status:visible")
          .getByText("Rückmeldung wird erstellt ...")
      ).toBeVisible();
      await completeQueuedFeedbackDeterministically({
        courseId: seeded.courseId,
        taskId: seeded.taskId,
        learnerSub
      });
    } finally {
      await releaseProviderWorker();
    }

    const finalButton = learner.page.getByRole("button", {
      name: "Diese geprüfte Fassung endgültig abgeben"
    });
    await expect(editor).toContainText(reviewedText);
    await expect(finalButton).toBeEnabled();

    const localDraft = "Diese lokale Weiterarbeit besitzt noch keine neue Rückmeldung.";
    await editor.fill(localDraft);
    await expect(editor).toContainText(localDraft);
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

    const historyResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions?limit=10&offset=0`
    );
    expect(historyResponse.ok(), await historyResponse.text()).toBe(true);
    const history = await historyResponse.json() as Array<{ intent: string; text_body?: string | null }>;
    expect(history.filter((submission) => submission.intent === "submit")).toHaveLength(1);
    expect(history.find((submission) => submission.intent === "submit")?.text_body).toBe(reviewedText);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await expect(learner.page.getByRole("button", { name: "Erneut bearbeiten" })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});

test("@feature-detail finalizes the reviewed uploaded file", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
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

    const finalButton = learner.page.getByRole("button", { name: "Diese geprüfte Fassung endgültig abgeben" });
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
