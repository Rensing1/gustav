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

    const finalButton = learner.page.getByRole("button", { name: "Endgültig abgeben" });
    const responseGroup = learner.page.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    await expect(editor).toContainText(reviewedText);
    await expect(responseGroup.getByText("Rückmeldung", { exact: true })).toBeVisible();
    await expect(responseGroup.getByText("Rückmeldung", { exact: true })).toBeInViewport();
    await expect(responseGroup.getByText("Auswertung", { exact: true })).toBeVisible();
    await expect(responseGroup.getByText("Entwurf", { exact: true })).toBeVisible();
    await expect(finalButton).toBeEnabled();

    const editorBox = await editor.boundingBox();
    const responseBox = await responseGroup.boundingBox();
    expect(editorBox).not.toBeNull();
    expect(responseBox).not.toBeNull();
    expect(editorBox!.y).toBeLessThan(responseBox!.y);

    const reviseButton = responseGroup.getByRole("button", { name: "Überarbeiten" });
    await reviseButton.click();
    await expect(editor).toBeFocused();
    const answerFormat = learner.page.getByRole("group", { name: "Antwortform" });
    await expect(answerFormat).toBeInViewport();
    await expect(editor).toBeInViewport();
    const readyStatusBox = await learner.page
      .locator(".learning-task-feedback-status--active")
      .boundingBox();
    const answerFormatBox = await answerFormat.boundingBox();
    expect(readyStatusBox).not.toBeNull();
    expect(answerFormatBox).not.toBeNull();
    expect(answerFormatBox!.y).toBeGreaterThanOrEqual(readyStatusBox!.y + readyStatusBox!.height);

    const localDraft = "Diese lokale Weiterarbeit besitzt noch keine neue Rückmeldung.";
    await editor.fill(localDraft);
    await expect(editor).toContainText(localDraft);
    await expect(finalButton).toBeEnabled();

    await holdProviderWorker();
    try {
      await learner.page.getByRole("button", { name: "Neue Rückmeldung einholen" }).click();
      await expect(finalButton).toBeVisible();
      await expect(finalButton).toBeDisabled();
      await completeQueuedFeedbackDeterministically({
        courseId: seeded.courseId,
        taskId: seeded.taskId,
        learnerSub
      });
    } finally {
      await releaseProviderWorker();
    }

    await expect(finalButton).toBeEnabled();
    await expect(editor).toContainText(localDraft);

    const newerLocalDraft = "Diese noch neuere Überarbeitung besitzt keine Rückmeldung.";
    await editor.fill(newerLocalDraft);
    await expect(editor).toContainText(newerLocalDraft);

    const feedbackSummary = learner.page.getByText("Rückmeldung", { exact: true });
    const feedbackDisclosure = feedbackSummary.locator("..");
    await feedbackSummary.click();
    await expect(feedbackDisclosure).not.toHaveAttribute("open");
    await expect(editor).toContainText(newerLocalDraft);
    await feedbackSummary.click();
    await expect(feedbackDisclosure).toHaveAttribute("open");
    await expect(editor).toContainText(newerLocalDraft);

    let finalizationRequests = 0;
    await learner.page.route(`**/learning/courses/${seeded.courseId}/units/${seeded.unitId}**`, async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      const form = new URLSearchParams(route.request().postData() ?? "");
      if (form.get("submission_intent") === "submit") {
        finalizationRequests += 1;
        await new Promise((resolve) => setTimeout(resolve, 600));
      }
      await route.continue();
    });

    await finalButton.click();
    const warning = learner.page.getByRole("dialog", { name: "Überarbeitung noch nicht geprüft" });
    await expect(warning).toBeVisible();
    await expect(warning).toContainText(
      "Endgültig abgegeben wird der Entwurf, zu dem du die Rückmeldung erhalten hast – nicht deine aktuelle Überarbeitung."
    );
    expect(finalizationRequests).toBe(0);

    await warning.getByRole("button", { name: "Weiter überarbeiten" }).click();
    await expect(warning).toBeHidden();
    await expect(editor).toBeFocused();
    await expect(editor).toContainText(newerLocalDraft);
    await finalButton.click();
    const confirmFinalization = warning.getByRole("button", { name: "Trotzdem abgeben" });
    await confirmFinalization.evaluate((button: HTMLButtonElement) => {
      button.click();
      button.click();
    });

    const status = learner.page.locator(".learning-task-feedback-status").getByRole("status");
    await expect(status).toContainText("Abgabe wird verarbeitet ...");
    await expect(finalButton).toBeDisabled();
    await expect(learner.page.getByRole("button", { name: "Neue Rückmeldung einholen" })).toBeDisabled();
    await expect(status).toContainText("Aufgabe abgegeben");
    expect(finalizationRequests).toBe(1);

    const completion = learner.page.getByRole("region", { name: "Aufgabe abgeschlossen" });
    await expect(completion.getByText("Aufgabe abgegeben.", { exact: true })).toBeVisible();
    await expect(completion.getByRole("button", { name: "Zurück zum Modul" })).toBeVisible();
    await expect(completion.getByRole("button")).toHaveCount(1);

    const historyResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions?limit=10&offset=0`
    );
    expect(historyResponse.ok(), await historyResponse.text()).toBe(true);
    const history = await historyResponse.json() as Array<{ intent: string; text_body?: string | null }>;
    expect(history.filter((submission) => submission.intent === "submit")).toHaveLength(1);
    expect(history.find((submission) => submission.intent === "submit")?.text_body).toBe(localDraft);

    await completion.getByRole("button", { name: "Zurück zum Modul" }).click();
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}$`)
    );
    const editAgainButton = learner.page.getByRole("button", { name: "Erneut bearbeiten" });
    await expect(editAgainButton).toBeVisible();
    await editAgainButton.click();
    await expect(editor).toContainText(newerLocalDraft);

    await holdProviderWorker();
    try {
      await learner.page.getByRole("button", { name: "Neue Rückmeldung einholen" }).click();
      await expect(finalButton).toBeVisible();
      await expect(finalButton).toBeDisabled();
      await completeQueuedFeedbackDeterministically({
        courseId: seeded.courseId,
        taskId: seeded.taskId,
        learnerSub
      });
    } finally {
      await releaseProviderWorker();
    }

    await expect(finalButton).toBeEnabled();
    await expect(editor).toContainText(newerLocalDraft);
    await expect(learner.page.getByRole("region", { name: "Aufgabe abgeschlossen" })).toHaveCount(0);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }

  await verifyPersistenceEquivalentTextDraft(browser);
});

async function verifyPersistenceEquivalentTextDraft(browser: Browser): Promise<void> {
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
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Getrimmte Abgabe ${unique}`);
    const reviewedText = "Diese Fassung endet lokal mit einer Leerzeile.";

    await learner.page.goto(`/learning/courses/${seeded.courseId}`);
    await learner.page.getByRole("link", { name: seeded.unitTitle }).click();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();

    const editor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await editor.fill(reviewedText);
    await editor.press("End");
    await editor.press("Enter");

    await holdProviderWorker();
    try {
      await learner.page.getByRole("button", { name: "Rückmeldung einholen" }).click();
      await completeQueuedFeedbackDeterministically({
        courseId: seeded.courseId,
        taskId: seeded.taskId,
        learnerSub
      });
    } finally {
      await releaseProviderWorker();
    }

    const finalButton = learner.page.getByRole("button", { name: "Endgültig abgeben" });
    await expect(finalButton).toBeEnabled();
    await finalButton.click();
    await expect(learner.page.getByRole("dialog", { name: "Überarbeitung noch nicht geprüft" })).toBeHidden();

    const status = learner.page.locator(".learning-task-feedback-status").getByRole("status");
    await expect(status).toContainText("Aufgabe abgegeben");
    const historyResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions?limit=10&offset=0`
    );
    expect(historyResponse.ok(), await historyResponse.text()).toBe(true);
    const history = await historyResponse.json() as Array<{ intent: string; text_body?: string | null }>;
    expect(history.filter((submission) => submission.intent === "submit")).toHaveLength(1);
    expect(history.find((submission) => submission.intent === "submit")?.text_body).toBe(reviewedText);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
}

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

    const finalButton = learner.page.getByRole("button", { name: "Endgültig abgeben" });
    await expect(learner.page.getByText("Datei", { exact: true })).toBeVisible();
    await expect(learner.page.getByRole("region", { name: "Bisherige Datei" })).toContainText("Aktuelle Datei");
    await expect(finalButton).toBeEnabled();

    await learner.page.getByLabel("Datei auswählen").setInputFiles({
      name: "neue-ausarbeitung.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n% Browserprüfung der neuen Dateiauswahl\n", "utf-8")
    });
    await expect(learner.page.getByRole("region", { name: "Ausgewählte Datei" })).toContainText(
      "neue-ausarbeitung.pdf"
    );
    await expect(finalButton).toBeDisabled();
    await expect(learner.page.getByText("Für die neue Datei zuerst Rückmeldung einholen.")).toBeVisible();

    await learner.page.reload();
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
