import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { seedLearnerVisualSmokeCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance reads a document stack without losing the active task", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `book_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `book_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, `Buchseite ${unique}`);

    await learner.page.setViewportSize({ width: 1920, height: 1080 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /beginnen/i }).first().click();

    const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const book = workbench.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const exercise = workbench.getByRole("main", { name: "Bearbeitung" });
    await expect(book).toBeVisible();
    await expect(exercise).toBeVisible();

    await book.getByRole("button", { name: "Perspektiven im Überblick ein- oder ausklappen" }).click();
    const image = book.getByRole("img", { name: seeded.imageAltText });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    await expect(image).toHaveAttribute("loading", "lazy");
    await book.getByRole("button", { name: `${seeded.pdfMaterialTitle} ein- oder ausklappen` }).click();
    await expect(book.getByTitle(`Material ${seeded.pdfMaterialTitle}`)).toBeVisible();

    await book.getByText("Weitere Materialien und eigene Abgaben", { exact: true }).click();
    const additionalContext = book.locator(".learner-material-context--compact");
    await expect(additionalContext).toBeVisible();
    await expect(additionalContext.locator(".learner-material-context__tree-children")).toHaveCount(0);
    const ownSubmissions = additionalContext.getByRole("button", { name: /Eigene Abgaben in Start/ });
    await expect(ownSubmissions).toHaveAttribute("aria-expanded", "false");
    await ownSubmissions.click();
    const previousSubmission = book.getByRole("button", {
      name: `${seeded.previousTaskLabel} ein- oder ausklappen`
    });
    await expect(previousSubmission).toBeVisible();
    const hierarchy = await additionalContext.evaluate((context) => {
      const moduleTitle = context.querySelector<HTMLElement>(
        ".learner-material-context__module--current > .learner-material-context__module-header h4"
      );
      const submissionGroup = context.querySelector<HTMLElement>(
        ".learner-material-context__submissions-toggle span"
      );
      const submissionTitle = context.querySelector<HTMLElement>(
        ".learner-material-context__tree-item--submission .learner-reference-document__toggle strong"
      );
      if (!moduleTitle || !submissionGroup || !submissionTitle) {
        throw new Error("Material tree hierarchy is incomplete");
      }
      return {
        moduleX: moduleTitle.getBoundingClientRect().left,
        submissionGroupX: submissionGroup.getBoundingClientRect().left,
        submissionX: submissionTitle.getBoundingClientRect().left
      };
    });
    expect(hierarchy.submissionGroupX).toBeGreaterThanOrEqual(hierarchy.moduleX);
    expect(hierarchy.submissionX).toBeGreaterThan(hierarchy.submissionGroupX);
    await previousSubmission.click();
    await expect(book.getByText(seeded.previousSubmissionText)).toBeVisible();
    await expect(workbench.getByRole("region", { name: "Dokument groß lesen" })).toHaveCount(0);

    await expect(exercise.locator(".learning-markdown-editor__toolbar")).toBeVisible();
    const editor = exercise.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await editor.fill("Dieser Entwurf muss während des Lesens erhalten bleiben.");
    await book.getByRole("button", { name: `${seeded.longMaterialTitle} groß lesen` }).click();
    const reader = workbench.getByRole("region", { name: "Dokument groß lesen" });
    await expect(reader).toBeVisible();
    await expect(reader.getByText("Vertiefung für die Großansicht")).toBeVisible();
    await learner.page.reload();
    await expect(reader).toBeVisible();
    await expect(reader.getByText("Vertiefung für die Großansicht")).toBeVisible();
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    await expect(editor).toHaveText("Dieser Entwurf muss während des Lesens erhalten bleiben.");

    const desktopScroll = await workbench.evaluate(() => {
      const bookScroll = document.querySelector<HTMLElement>(".learner-task-context__scroll");
      const workScroll = document.querySelector<HTMLElement>(".learner-task-workbench__main");
      if (!bookScroll || !workScroll) throw new Error("work surfaces missing");
      bookScroll.scrollTop = 80;
      return { book: bookScroll.scrollTop, work: workScroll.scrollTop };
    });
    expect(desktopScroll.book).toBeGreaterThan(0);
    expect(desktopScroll.work).toBe(0);

    for (const viewport of [
      { width: 820, height: 1180 },
      { width: 390, height: 844 }
    ]) {
      await learner.page.setViewportSize(viewport);
      await expect(workbench.getByRole("button", { name: "Aufgabe", exact: true })).toBeVisible();
      await expect(book).toBeVisible();
      await expect(exercise).toBeHidden();
      const touchTargets = await book.locator(
        ".learner-material-context__module-toggle, .learner-material-context__submissions-toggle, .learner-reference-document__toggle, .learner-reference-document__icon-action"
      ).evaluateAll((elements) => elements.filter((element) => {
        const styles = getComputedStyle(element);
        return styles.display !== "none" && styles.visibility !== "hidden";
      }).map((element) => element.getBoundingClientRect().height));
      expect(Math.min(...touchTargets)).toBeGreaterThanOrEqual(44);
      await expectNoViewportOverflow(learner.page);
    }
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
