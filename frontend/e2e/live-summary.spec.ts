import { currentUserSub, login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse, seedLearnerPracticeCourse } from "./support/seed-data";
import { completeQueuedFeedbackDeterministically, holdProviderWorker, releaseProviderWorker } from "./support/submission-finalization-fixture";

test("@feature-acceptance teacher opens the ordered live task summary and retains selection", async ({ browser }) => {
  test.setTimeout(120_000);
  const teacherEmail = e2eEmail("live-teacher");
  const learnerEmail = e2eEmail("live-learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  teacherContext.setDefaultTimeout(15_000);
  learnerContext.setDefaultTimeout(15_000);
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, "Live-Reihenfolge");

    await teacher.getByRole("link", { name: "Live", exact: true }).click();
    await teacher.getByRole("combobox", { name: "Kurs", exact: true }).selectOption(seeded.courseId);
    await teacher.getByRole("combobox", { name: "Lerneinheit", exact: true }).selectOption(seeded.unitId);
    await expect(teacher.getByRole("heading", { name: "Klassenübersicht" })).toBeVisible();
    const matrix = teacher.getByRole("region", { name: "Lernaufgaben nach Schülern" });
    await expect(matrix.locator("tbody tr")).toHaveCount(1);
    await expect(matrix.getByRole("columnheader", { name: "Grundlagen", exact: true })).toBeVisible();
    await expect(matrix.getByRole("columnheader", { name: "Quellen", exact: true })).toBeVisible();
    await matrix.locator(".live-score").first().click();

    const taskLinks = teacher.getByRole("navigation", { name: "Aufgaben der Lerneinheit" }).getByRole("link");
    await expect(taskLinks).toHaveCount(3);
    for (const [index, id] of [seeded.taskId, seeded.secondTaskId, seeded.contextTaskId].entries()) {
      await expect(taskLinks.nth(index)).toHaveAttribute("href", new RegExp(`task_id=${id}`));
    }
    await taskLinks.nth(2).click();
    await expect(teacher).toHaveURL(new RegExp(`task_id=${seeded.contextTaskId}`));
    await teacher.reload();
    await expect(taskLinks.nth(2)).toHaveClass(/is-active/);
    await expect(teacher.getByRole("complementary", { name: "Schülerdetail" })).toContainText("Keine Abgabe");

    const forbidden = await learner.request.get(
      `/api/teaching/courses/${seeded.courseId}/units/${seeded.unitId}/submissions/summary`
    );
    expect(forbidden.status()).toBe(403);

    // Submit through the real learner UI; only the external AI result is deterministic.
    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}`);
    await learner.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const answer = "Beide Materialien zeigen, wie Grundrechte die digitale Kommunikation und Überwachung begrenzen.";
    await learner.locator('.learning-markdown-editor__surface [contenteditable="true"]').fill(answer);
    await holdProviderWorker();
    try {
      await learner.getByRole("button", { name: "Rückmeldung einholen", exact: true }).click();
      await expect(learner.locator(".learning-task-feedback-status:visible")).toContainText("Rückmeldung wird erstellt");
      await completeQueuedFeedbackDeterministically({ ...seeded, learnerSub: await currentUserSub(learner) });
      await expect(learner.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
      await learner.getByRole("button", { name: "Endgültig abgeben" }).click();
      await expect(learner.getByRole("region", { name: "Aufgabe abgeschlossen" })).toBeVisible();
    } finally {
      await releaseProviderWorker();
    }
    // No teacher reload: polling must update the matrix in place.
    await expect(matrix.locator(".live-score").first()).not.toHaveText("–", { timeout: 30_000 });
    await matrix.locator(".live-score").first().click();
    await expect(teacher.getByRole("tabpanel", { name: "Abgabe", exact: true })).toContainText(answer);
    const instruction = teacher.locator(".live-panel-summary__context");
    const initialWidth = (await instruction.boundingBox())!.width;
    for (const label of ["Rückmeldung", "Auswertung", "Abgabe"]) {
      await teacher.getByRole("tab", { name: label, exact: true }).click();
      await expect(teacher.getByRole("tabpanel", { name: label, exact: true })).toBeVisible();
      expect((await instruction.boundingBox())!.width).toBeCloseTo(initialWidth, 1);
    }

    // Practice stays a separate matrix and supports the same detail navigation.
    const practice = await seedLearnerPracticeCourse(teacher, learner, "Live-Übungsmatrix");
    await teacher.getByRole("link", { name: "Live", exact: true }).click();
    await teacher.getByRole("combobox", { name: "Kurs", exact: true }).selectOption(practice.courseId);
    await teacher.getByRole("combobox", { name: "Lerneinheit", exact: true }).selectOption(practice.unitId);
    await teacher.getByRole("radio", { name: "Üben", exact: true }).press("Space");
    const practiceMatrix = teacher.getByRole("region", { name: "Übungsmodule nach Schülern" });
    await practiceMatrix.getByRole("button", { name: /Übungsmodul Wiederholen: Fällig/ }).click();
    const detail = teacher.getByRole("complementary", { name: "Schülerdetail" });
    await expect(detail).toContainText("Erkläre, warum ein Test zuerst rot sein soll.");
    await expect(detail).toContainText("Keine Abgabe");
    await teacher.reload();
    await expect(teacher.getByRole("radio", { name: "Üben", exact: true })).toBeChecked();
    await teacher.setViewportSize({ width: 390, height: 844 });
    await expect(teacher.getByRole("combobox", { name: "Übungsmodul", exact: true })).toBeVisible();
    expect(await teacher.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const tableBounds = await practiceMatrix.boundingBox();
    const detailBounds = await detail.boundingBox();
    expect(detailBounds!.y).toBeGreaterThan(tableBounds!.y + tableBounds!.height);
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
