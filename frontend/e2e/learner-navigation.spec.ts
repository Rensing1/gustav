import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import {
  seedLearnerNavigationCourse,
  seedLearnerVisualSmokeCourse
} from "./support/seed-data";
import {
  completeQueuedFeedbackDeterministically,
  holdProviderWorker,
  releaseProviderWorker
} from "./support/submission-finalization-fixture";


async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

async function requestDeterministicFeedback({
  page,
  courseId,
  taskId,
  learnerSub
}: {
  page: Page;
  courseId: string;
  taskId: string;
  learnerSub: string;
}) {
  await holdProviderWorker();
  try {
    await page.getByRole("button", { name: "Rückmeldung einholen" }).click();
    await expect(
      page.locator(".learning-task-feedback-status:visible").getByText("Rückmeldung wird erstellt ...")
    ).toBeVisible();
    await completeQueuedFeedbackDeterministically({ courseId, taskId, learnerSub });
  } finally {
    await releaseProviderWorker();
  }
  await expect(page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
}

test("@feature-acceptance follows graph, reading, task and deterministic feedback as one learning path", async ({ browser }) => {
  test.setTimeout(240_000);
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

    const unitPath = `/learning/courses/${seeded.courseId}/units/${seeded.unitId}`;
    const modulePath = `${unitPath}?module=${seeded.graphModuleId}`;
    const taskPath = `${modulePath}&task=${seeded.taskId}`;

    await learner.page.goBack();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));
    await learner.page.goForward();
    await expect(learner.page).toHaveURL(new RegExp(`task=${seeded.taskId}$`));
    await expect(editor).toContainText("klare und überprüfbare Regeln");

    await learner.page.goto(`/learning/courses/${seeded.courseId}`);
    await learner.page.goto(modulePath);
    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.page).toHaveURL(new RegExp(`${unitPath}$`));
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();

    await learner.page.goto(`/learning/courses/${seeded.courseId}`);
    await learner.page.goto(taskPath);
    await learner.page.getByRole("button", { name: /← Zurück zu Modul Grundlagen/ }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));

    await learner.page.goto(taskPath);
    await learner.page.reload();
    await learner.page.getByRole("button", { name: /← Zurück zu Modul Grundlagen/ }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));

    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await editor.fill("Digitale Kommunikation braucht klare und überprüfbare Regeln.");
    await expect(editor).toContainText("klare und überprüfbare Regeln");
    await requestDeterministicFeedback({
      page: learner.page,
      courseId: seeded.courseId,
      taskId: seeded.taskId,
      learnerSub
    });
    await learner.page.goto(
      `/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}&panel=result`
    );

    const response = learner.page.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    await expect(response).toBeVisible();
    await expect(response).toContainText(
      "Die Antwort erklärt den Gedanken nachvollziehbar und kann jetzt weiterverwendet werden."
    );
    await learner.page.getByRole("button", { name: "Endgültig abgeben" }).click();
    const firstCompletion = learner.page.getByRole("region", { name: "Aufgabe abgeschlossen" });
    await expect(firstCompletion.getByRole("button", { name: "Zurück zum Modul" })).toBeVisible();
    await firstCompletion.getByRole("button", { name: "Zurück zum Modul" }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));

    await learner.page.getByRole("button", { name: "Aufgabe 2 beginnen" }).click();
    const secondEditor = learner.page.locator(
      '.learning-markdown-editor__surface [contenteditable="true"]'
    );
    await secondEditor.fill("Die Materialien setzen unterschiedliche Schwerpunkte.");
    await requestDeterministicFeedback({
      page: learner.page,
      courseId: seeded.courseId,
      taskId: seeded.secondTaskId,
      learnerSub
    });
    await learner.page.getByRole("button", { name: "Endgültig abgeben" }).click();
    const finalCompletion = learner.page.getByRole("region", { name: "Aufgabe abgeschlossen" });
    await expect(finalCompletion.getByRole("button", { name: "Zurück zum Lernpfad" })).toBeVisible();
    await finalCompletion.getByRole("button", { name: "Zurück zum Lernpfad" }).click();
    await expect(learner.page).toHaveURL(new RegExp(`${unitPath}$`));
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();

    const linear = await seedLearnerVisualSmokeCourse(
      teacher.page,
      learner.page,
      `Linearer Rückweg ${unique}`
    );
    const linearUnitPath = `/learning/courses/${linear.courseId}/units/${linear.unitId}`;
    await learner.page.goto(`${linearUnitPath}?task=${linear.taskId}`);
    await learner.page.getByRole("button", { name: "← Zurück zu den Inhalten" }).click();
    await expect(learner.page).toHaveURL(new RegExp(`${linearUnitPath}$`));
    await expect(learner.page.getByRole("heading", { name: linear.unitTitle })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
