import { newBrowserContext } from "./support/browser-context";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { currentUserSub, login } from "./support/auth";
import { apiHeaders, expectApiOk } from "./support/api";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { seedLearnerVisualSmokeCourse } from "./support/seed-data";

const password = e2ePassword;

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await newBrowserContext(browser, { baseURL: webBase });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance reads a document stack without losing the active task", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
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
    // Verify the rendered design contract alongside the real authenticated workflow.
    await expect(book).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(exercise).toHaveCSS("border-radius", "8px");
    await expect(workbench.locator(".learner-task-workbench__desk")).toHaveCSS("column-gap", "0px");
    await expect(workbench.locator(".learner-task-workbench__desk")).toHaveCSS(
      "grid-template-columns", /\d+(?:\.\d+)?px 16px \d+(?:\.\d+)?px/
    );

    const reader = workbench.getByRole("region", { name: "Dokument groß lesen" });
    const outline = book.locator(".workspace-outline");
    await outline.getByRole("button", { name: /Perspektiven im Überblick/ }).click();
    const image = reader.getByRole("img", { name: seeded.imageAltText });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    await expect(image).toHaveAttribute("loading", "lazy");
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    await outline.getByRole("button", { name: seeded.pdfMaterialTitle + " Material", exact: true }).click();
    await expect(reader.getByTitle(`Material ${seeded.pdfMaterialTitle}`)).toBeVisible();
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    const previousSubmission = outline.getByRole("button", { name: `${seeded.previousTaskLabel} · Meine Abgabe`, exact: true });
    await previousSubmission.click();
    await expect(reader).toContainText(seeded.previousSubmissionText);
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();

    const editor = exercise.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    const draft = "Dieser Entwurf muss während des Lesens erhalten bleiben.";
    await editor.fill(draft);
    const openLongMaterial = () => outline.getByRole("button", { name: seeded.longMaterialTitle + " Material", exact: true }).click();
    await openLongMaterial();
    await expect(reader).toContainText("Vertiefung für die Großansicht");
    await learner.page.reload();
    await expect(reader).toContainText("Vertiefung für die Großansicht");
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    await expect(editor).toHaveText(draft);

    for (const viewport of [
      { width: 1024, height: 768 }, { width: 820, height: 1180 }, { width: 390, height: 844 }
    ]) {
      await learner.page.setViewportSize(viewport);
      if (!(await book.isVisible())) await workbench.getByRole("button", { name: "Materialien", exact: true }).click();
      await expect(book).toBeVisible();
      await expect(outline).toBeVisible();
      await previousSubmission.click();
      await expect(reader).toContainText(seeded.previousSubmissionText);
      await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
      if (!(await exercise.isVisible())) await workbench.getByRole("button", { name: "Aufgabe", exact: true }).click();
      await expect(editor).toHaveText(draft);
      if (!(await book.isVisible())) await workbench.getByRole("button", { name: "Materialien", exact: true }).click();
      await openLongMaterial();
      await expect(reader).toContainText("Vertiefung für die Großansicht");
      await reader.locator(".learner-reference-document").scrollIntoViewIfNeeded();
      await expectNoViewportOverflow(learner.page);
      await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    }

    const removed = await teacher.page.request.delete(
      `${webBase}/api/teaching/courses/${seeded.courseId}/members/${await currentUserSub(learner.page)}`,
      { headers: apiHeaders() }
    );
    await expectApiOk(removed, 204);
    for (const path of [
      `/api/learning/courses/${seeded.courseId}/sections`,
      `/api/learning/courses/${seeded.courseId}/units/${seeded.unitId}/sections`
    ]) {
      const denied = await learner.page.request.get(`${webBase}${path}?include=materials,tasks`);
      expect(denied.status()).toBe(403);
      expect(denied.headers()["cache-control"]).toBe("private, no-store");
    }
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
