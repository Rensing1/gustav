import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";
import {
  completeQueuedFeedbackDeterministically,
  holdProviderWorker,
  releaseProviderWorker
} from "./support/submission-finalization-fixture";


async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance follows graph, reading, task and deterministic feedback as one learning path", async ({ browser }) => {
  test.setTimeout(120_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, e2ePassword);
    await login(learner.page, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(
      teacher.page,
      learner.page,
      `Lernweg ${unique}`
    );
    const learnerSub = await currentUserSub(learner.page);

    await learner.page.goto(`/learning/courses/${seeded.courseId}`);
    await learner.page.getByRole("link", { name: seeded.unitTitle }).click();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));
    await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
    await expect(learner.page.getByTitle(seeded.secondMaterialTitle)).toBeVisible();

    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const editor = learner.page.locator(
      '.learning-markdown-editor__surface [contenteditable="true"]'
    );
    await editor.fill("Digitale Kommunikation braucht klare und überprüfbare Regeln.");
    await expect(editor).toContainText("klare und überprüfbare Regeln");

    // The browser creates the real submission and queue job. Only provider
    // execution is held while the existing job receives deterministic output.
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
    await learner.page.goto(
      `/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}&panel=result`
    );

    const response = learner.page.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    await expect(response).toBeVisible();
    await expect(response).toContainText(
      "Die Antwort erklärt den Gedanken nachvollziehbar und kann jetzt weiterverwendet werden."
    );
    await expect(
      learner.page.getByRole("button", { name: "Diesen Entwurf endgültig abgeben" })
    ).toBeEnabled();

    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
