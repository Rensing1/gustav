import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance follows graph, reading and task as one authenticated learning path", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `navigation_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `navigation_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Lernweg ${unique}`);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));
    await expect(learner.page.getByText("Dieses Material ist beim ersten Lesen vollständig geöffnet.")).toBeVisible();

    await learner.page.getByRole("button", { name: /beginnen/i }).click();
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}&task=${seeded.taskId}$`)
    );
    await expect(learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" })).toBeVisible();
    await expectNoViewportOverflow(learner.page);

    await learner.page.goBack();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));
    await expect(learner.page.getByRole("heading", { name: "Grundlagen" })).toBeVisible();
    await learner.page.goBack();
    await expect(learner.page).toHaveURL(new RegExp(`/units/${seeded.unitId}$`));
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
