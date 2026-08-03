import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { currentUserSub, login } from "./support/auth";
import { prepareCompletedDialogTurn } from "./support/dialog-session-fixture";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerDialogCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance learner deliberately enters and resumes dialog completion", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_dialog_learning_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_dialog_learning_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerDialogCourse(teacher.page, learner.page, `Dialog Lernen ${unique}`);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
    await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
    await expect(learner.page.getByRole("region", { name: "KI-Dialog" })).toBeVisible();
    await expect(learner.page.getByText("Welche Beobachtung möchtest du zuerst untersuchen?")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();
    await expect(learner.page.getByRole("button", { name: "Dialog beenden" })).toBeHidden();

    const sessionId = await prepareCompletedDialogTurn({
      courseId: seeded.courseId,
      taskId: seeded.taskId,
      learnerSub
    });
    const storageKey = `gustav.learning.dialog-closing-draft:${encodeURIComponent(learnerSub)}:${seeded.courseId}:${seeded.taskId}:${sessionId}`;

    await learner.page.reload();
    await expect(learner.page.getByText("Welche Textstelle belegt diese Beobachtung?")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();
    await learner.page.getByRole("button", { name: "Dialog beenden" }).click();

    const closingField = learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.");
    await expect(closingField).toBeVisible();
    await closingField.fill("Die Auswahl der Textstellen bestimmt die Perspektive.");
    await expect(learner.page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();

    await learner.page.reload();
    await expect(learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.")).toHaveValue(
      "Die Auswahl der Textstellen bestimmt die Perspektive."
    );
    await learner.page.getByRole("button", { name: "Zurück zum Dialog" }).click();
    await expect(learner.page.getByLabel("Deine Antwort (1/2)")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();

    await learner.page.getByRole("button", { name: "Dialog beenden" }).click();
    await expect(learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.")).toHaveValue(
      "Die Auswahl der Textstellen bestimmt die Perspektive."
    );
    await learner.page.getByRole("button", { name: "Endgültig abgeben" }).click();

    await expect(learner.page.getByText("Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.")).toBeVisible();
    expect(await learner.page.evaluate((key) => window.sessionStorage.getItem(key), storageKey)).toBeNull();
    const sessionResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/dialog-sessions/${sessionId}`
    );
    expect(sessionResponse.ok(), await sessionResponse.text()).toBe(true);
    expect((await sessionResponse.json()).status).toBe("completed");
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
