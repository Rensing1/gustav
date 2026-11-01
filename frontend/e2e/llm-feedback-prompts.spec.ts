import { apiHeaders, expectApiOk } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { completeDialogFeedback, prepareCompletedDialogTurn } from "./support/dialog-session-fixture";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Browser, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerDialogCourse, seedLearnerNavigationCourse } from "./support/seed-data";
import {
  completeQueuedFeedbackDeterministically,
  holdProviderWorker,
  releaseProviderWorker
} from "./support/submission-finalization-fixture";

const internalContext = "Interner Prüfmarker: GUSTAV-PROMPT-CONTEXT. Zulässige Varianten berücksichtigen; knapp und ohne feste Überschriften antworten.";

async function participants(browser: Browser) {
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser, { baseURL: webBase });
  const learnerContext = await newBrowserContext(browser, { baseURL: webBase });
  const teacher = await teacherContext.newPage();
  const learner = await learnerContext.newPage();
  await login(teacher, teacherEmail, e2ePassword);
  await login(learner, learnerEmail, e2ePassword);
  return { teacher, learner, close: async () => {
    await learnerContext.close();
    await teacherContext.close();
  } };
}

async function setTeacherContext(teacher: Page, seeded: { unitId: string; sectionId: string; taskId: string }) {
  const response = await teacher.request.patch(
    `${webBase}/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}/tasks/${seeded.taskId}`,
    { headers: apiHeaders(), data: { teacher_context_md: internalContext } }
  );
  await expectApiOk(response);
}

async function submissionHistory(learner: Page, courseId: string, taskId: string) {
  const response = await learner.request.get(
    `${webBase}/api/learning/courses/${courseId}/tasks/${taskId}/submissions?limit=10&offset=0`
  );
  await expectApiOk(response);
  const body = await response.text();
  expect(body).not.toContain("teacher_context_md");
  expect(body).not.toContain("GUSTAV-PROMPT-CONTEXT");
  return JSON.parse(body);
}

async function verifyTextFeedback(browser: Browser) {
  const people = await participants(browser);
  try {
    const { teacher, learner } = people;
    const seeded = await seedLearnerNavigationCourse(teacher, learner, "Promptintegration Text");
    await setTeacherContext(teacher, seeded);
    const learnerSub = await currentUserSub(learner);
    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const editor = learner.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await editor.fill("Beide Materialien beschreiben einen Konflikt zwischen Freiheit und Sicherheit.");

    await holdProviderWorker();
    try {
      await learner.getByRole("button", { name: "Rückmeldung einholen" }).click();
      await completeQueuedFeedbackDeterministically({ courseId: seeded.courseId, taskId: seeded.taskId, learnerSub });
    } finally {
      await releaseProviderWorker();
    }

    const feedback = "Die Antwort erklärt den Gedanken nachvollziehbar und kann jetzt weiterverwendet werden.";
    await expect(learner.getByText(feedback, { exact: true })).toBeVisible();
    await expect(learner.getByText("GUSTAV-PROMPT-CONTEXT", { exact: false })).toHaveCount(0);
    const before = await submissionHistory(learner, seeded.courseId, seeded.taskId);
    expect(before[0].analysis_status).toBe("completed");
    expect(before[0].analysis_json.criteria_results).toHaveLength(2);
    expect(before[0].feedback_md).toBe(feedback);

    await learner.reload();
    await learner.getByText("Rückmeldung", { exact: true }).click();
    await expect(learner.getByText(feedback, { exact: true })).toBeVisible();
    await learner.getByText("Auswertung", { exact: true }).click();
    await expect(learner.getByRole("list", { name: "Bewertungskriterien" })).toBeVisible();
    const after = await submissionHistory(learner, seeded.courseId, seeded.taskId);
    expect(after[0].analysis_json).toEqual(before[0].analysis_json);
    expect(after[0].feedback_md).toBe(feedback);
  } finally {
    await people.close();
  }
}

async function verifyDialogFeedback(browser: Browser) {
  const people = await participants(browser);
  try {
    const { teacher, learner } = people;
    const seeded = await seedLearnerDialogCourse(teacher, learner, "Promptintegration Dialog");
    await setTeacherContext(teacher, seeded);
    const learnerSub = await currentUserSub(learner);
    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.getByRole("button", { name: /beginnen/i }).first().click();
    await expect(learner.getByRole("region", { name: "KI-Dialog" })).toBeVisible();
    await expect(learner.getByText("Welche Beobachtung möchtest du zuerst untersuchen?", { exact: true })).toBeVisible();
    const sessionId = await prepareCompletedDialogTurn({ courseId: seeded.courseId, taskId: seeded.taskId, learnerSub });
    await learner.reload();
    await learner.getByRole("button", { name: "Zur Abschlussaufgabe" }).click();
    await learner.getByLabel("Deine Antwort", { exact: true }).fill("Die Auswahl der Textstellen bestimmt die Perspektive.");
    const feedback = "Sie erklären nachvollziehbar, wie die Auswahl der Textstellen die Perspektive bestimmt.";

    await holdProviderWorker();
    try {
      await learner.getByRole("button", { name: "Gespräch und Antwort abgeben", exact: true }).click();
      await expect(learner.getByRole("region", { name: "Deine Bearbeitung", exact: true })).toBeVisible();
      await completeDialogFeedback({ sessionId, feedbackMd: feedback });
    } finally {
      await releaseProviderWorker();
    }

    await expect(learner.getByText(feedback, { exact: true })).toBeVisible();
    const before = await submissionHistory(learner, seeded.courseId, seeded.taskId);
    expect(before[0].analysis_status).toBe("completed");
    expect(before[0].analysis_json.criteria_results ?? []).toHaveLength(0);
    expect(before[0].feedback_md).toBe(feedback);
    await learner.reload();
    await expect(learner.getByText(feedback, { exact: true })).toBeVisible();
    await expect(learner.getByRole("list", { name: "Bewertungskriterien" })).toHaveCount(0);
    await expect(learner.getByText("GUSTAV-PROMPT-CONTEXT", { exact: false })).toHaveCount(0);
    const after = await submissionHistory(learner, seeded.courseId, seeded.taskId);
    expect(after[0].feedback_md).toBe(feedback);
  } finally {
    await people.close();
  }
}


test("@feature-acceptance text and dialog feedback persist without exposing teacher context", async ({ browser }) => {
  test.setTimeout(180_000);
  await verifyTextFeedback(browser);
  await verifyDialogFeedback(browser);
});
