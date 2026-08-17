import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance keeps text drafts separated by task", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `task_drafts_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `task_drafts_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Aufgabenentwürfe ${unique}`);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();

    const editor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await editor.fill("Entwurf für Aufgabe 1");
    await learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" }).click();

    await learner.page.getByRole("button", { name: "Aufgabe 2 beginnen" }).click();
    await expect(editor).toHaveText("");
    await editor.fill("Entwurf für Aufgabe 2");
    await learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" }).click();

    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(editor).toContainText("Entwurf für Aufgabe 1");
    await learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" }).click();

    await learner.page.getByRole("button", { name: "Aufgabe 2 beginnen" }).click();
    await expect(editor).toContainText("Entwurf für Aufgabe 2");
    await learner.page.reload();
    await expect(editor).toContainText("Entwurf für Aufgabe 2");
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
