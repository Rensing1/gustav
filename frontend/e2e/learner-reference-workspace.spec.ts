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

    const image = book.getByRole("img", { name: seeded.imageAltText });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    await expect(image).toHaveAttribute("loading", "lazy");
    await expect(book.getByTitle(`Material ${seeded.pdfMaterialTitle}`)).toBeVisible();

    await book.getByRole("button", { name: "Kontext hinzufügen" }).click();
    await book.getByRole("button", { name: /Aktuelles Modul/ }).click();
    const previousSubmission = book.getByRole("button", {
      name: new RegExp(`Eigene frühere Abgabe.*${seeded.previousTaskLabel}`)
    });
    await expect(previousSubmission).toBeVisible();
    await previousSubmission.click();
    await expect(book.getByText(seeded.previousSubmissionText)).toBeVisible();
    await expect(workbench.getByRole("region", { name: "Dokument groß lesen" })).toHaveCount(0);

    const editor = exercise.getByRole("textbox");
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
      { width: 1024, height: 768 },
      { width: 390, height: 844 }
    ]) {
      await learner.page.setViewportSize(viewport);
      await expect(workbench.getByRole("button", { name: "Aufgabe", exact: true })).toBeVisible();
      await expect(book).toBeVisible();
      await expect(exercise).toBeHidden();
      await expectNoViewportOverflow(learner.page);
    }
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
