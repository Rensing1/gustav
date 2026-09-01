import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = e2ePassword;
type DraftMetrics = { draftWrites: number; longTasks: number[] };

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, hasTouch: true });
  await context.addInitScript(() => {
    const originalSetItem = Storage.prototype.setItem;
    const metrics: DraftMetrics = { draftWrites: 0, longTasks: [] };
    (window as Window & { __gustavDraftMetrics?: DraftMetrics }).__gustavDraftMetrics = metrics;
    Storage.prototype.setItem = function setItem(key: string, value: string) {
      if (key.startsWith("gustav.learning.submission-draft:")) {
        metrics.draftWrites += 1;
      }
      return originalSetItem.call(this, key, value);
    };
    if (PerformanceObserver.supportedEntryTypes.includes("longtask")) {
      new PerformanceObserver((list) => {
        metrics.longTasks.push(...list.getEntries().map((entry) => entry.duration));
      }).observe({ type: "longtask", buffered: true });
    }
  });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance keeps text drafts separated by task", async ({ browser }) => {
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
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Aufgabenentwürfe ${unique}`);

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();

    const editor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    const performanceDraft = "Eine flüssige Eingabe auf dem iPad bleibt vollständig erhalten. ".repeat(4).trim();
    await learner.page.evaluate(() => {
      const metrics = (window as Window & { __gustavDraftMetrics?: DraftMetrics }).__gustavDraftMetrics;
      if (metrics) {
        metrics.draftWrites = 0;
        metrics.longTasks = [];
      }
    });
    const typingStartedAt = Date.now();
    await editor.pressSequentially(performanceDraft);
    expect(Date.now() - typingStartedAt).toBeLessThan(4_000);
    expect(await learner.page.evaluate(
      () => (window as Window & { __gustavDraftMetrics?: DraftMetrics }).__gustavDraftMetrics?.draftWrites ?? 0
    )).toBeLessThan(5);
    expect(await learner.page.evaluate(
      () => Math.max(0, ...((window as Window & { __gustavDraftMetrics?: DraftMetrics }).__gustavDraftMetrics?.longTasks ?? []))
    )).toBeLessThan(1_000);
    await expect(editor).toContainText(performanceDraft);
    await expect.poll(() => learner.page.evaluate(
      () => (window as Window & { __gustavDraftMetrics?: DraftMetrics }).__gustavDraftMetrics?.draftWrites ?? 0
    )).toBeGreaterThan(0);
    await learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" }).click();

    await learner.page.getByRole("button", { name: "Aufgabe 2 beginnen" }).click();
    await expect(editor).toHaveText("");
    await editor.fill("Entwurf für Aufgabe 2");
    await learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" }).click();

    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(editor).toContainText(performanceDraft);
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
