import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { prepareCourseAiUsage } from "./support/ai-usage-fixture";
import { currentUserSub, login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedTeacherAiUsageCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance teacher sees combined submission and dialog token usage and filters a Berlin day", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_ai_usage_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_ai_usage_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedTeacherAiUsageCourse(teacher.page, learner.page, `E2E KI-Nutzung ${unique}`);
    await prepareCourseAiUsage({
      courseId: seeded.courseId,
      unitId: seeded.unitId,
      taskId: seeded.taskId,
      learnerSub
    });

    await teacher.page.goto(`/teaching/courses/${seeded.courseId}`);
    await teacher.page.getByRole("link", { name: "KI-Nutzung öffnen" }).click();
    await expect(teacher.page).toHaveURL(`/teaching/courses/${seeded.courseId}/ai-usage`);

    const summary = teacher.page.getByRole("region", { name: "Tokenübersicht" });
    await expect(summary.getByText("1.600")).toBeVisible();
    await expect(summary.getByText("400")).toBeVisible();
    await expect(summary.getByText("2.000")).toBeVisible();
    await expect(teacher.page.getByText("1 unbekannter Aufruf")).toBeVisible();
    const table = teacher.page.getByRole("table", { name: "Tokennutzung nach Modell und Nutzungsart" });
    await expect(table.getByRole("columnheader")).toHaveCount(5);
    await expect(table.getByText("model-submission")).toBeVisible();
    await expect(table.getByText("model-dialog").first()).toBeVisible();

    await teacher.page.getByLabel("Von").fill("2026-08-08");
    await teacher.page.getByLabel("Bis").fill("2026-08-08");
    await teacher.page.getByRole("button", { name: "Anwenden" }).click();

    await expect(summary.getByText("1.200")).toBeVisible();
    await expect(summary.getByText("300")).toBeVisible();
    await expect(summary.getByText("1.500")).toBeVisible();
    await expect(table.getByText("model-submission")).toBeVisible();
    await expect(table.getByText("model-dialog")).toHaveCount(0);
    await expect(teacher.page.getByText(/unbekannte[r]? Aufrufe?/)).toHaveCount(0);
  } finally {
    await teacher.context.close();
    await learner.context.close();
  }
});
