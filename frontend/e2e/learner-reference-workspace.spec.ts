import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { newBrowserContext } from "./support/browser-context";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { currentUserSub, login } from "./support/auth";
import { apiHeaders, expectApiOk } from "./support/api";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { seedH5pVisualSmokeUnit, seedLearnerVisualSmokeCourse } from "./support/seed-data";

const password = e2ePassword;

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await newBrowserContext(browser, { baseURL: webBase });
  return { context, page: await context.newPage() };
}

async function readDocumentStack(browser: Browser): Promise<void> {
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
    await expect(reader).toHaveCount(0);
    const image = outline.getByRole("img", { name: seeded.imageAltText });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    await expect(image).toHaveAttribute("loading", "lazy");
    await outline.getByRole("button", { name: seeded.pdfMaterialTitle + " Material", exact: true }).click();
    await expect(outline.getByTitle(`Material ${seeded.pdfMaterialTitle}`)).toBeVisible();
    await expect(image).toBeVisible();
    await expect(exercise).toBeVisible();
    const previousSubmission = outline.getByRole("button", { name: `${seeded.previousTaskLabel} · Meine Abgabe`, exact: true });
    await previousSubmission.click();
    await expect(reader).toContainText(seeded.previousSubmissionText);
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();

    const editor = exercise.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    const draft = "Dieser Entwurf muss während des Lesens erhalten bleiben.";
    await editor.fill(draft);
    const openLongMaterial = () => outline.getByRole("button", { name: seeded.longMaterialTitle + " Material", exact: true }).click();
    await openLongMaterial();
    await expect(outline).toContainText("Vertiefung für die Großansicht");
    await expect(reader).toHaveCount(0);
    await outline.getByRole("button", { name: seeded.longMaterialTitle + " groß lesen", exact: true }).click();
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
      const materialToggle = outline.getByRole("button", { name: seeded.longMaterialTitle + " Material", exact: true });
      if (await materialToggle.getAttribute("aria-expanded") !== "true") await materialToggle.click();
      await expect(outline).toContainText("Vertiefung für die Großansicht");
      await expectNoViewportOverflow(learner.page);
      await outline.getByRole("button", { name: seeded.longMaterialTitle + " groß lesen", exact: true }).click();
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
}

test("@feature-acceptance reads inline material without losing native or H5P work", async ({ browser }, info) => {
  test.setTimeout(180_000);
  await readDocumentStack(browser);
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedH5pVisualSmokeUnit(teacher.page, learner.page, `Material neben H5P ${Date.now()}`);
    const base = `/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}`;
    for (const nr of [1, 2]) {
      const response = await teacher.page.request.post(`${webBase}${base}/materials`, {
        headers: apiHeaders(), data: { title: `Nachschlagen ${nr}`, body_md: `Vollständiger Begleittext ${nr}.` }
      });
      await expectApiOk(response, 201);
    }
    const root = resolve(process.cwd(), "..");
    const fixture = resolve(root, "frontend/e2e/fixtures/h5p-multichoice-design");
    const archive = execFileSync(resolve(root, ".venv/bin/python"), ["-c", [
      "import io,pathlib,sys,zipfile", "b=io.BytesIO()",
      "with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:",
      " for p in pathlib.Path(sys.argv[1]).rglob('*'):",
      "  if p.is_file(): z.write(p,p.relative_to(sys.argv[1]))",
      "sys.stdout.buffer.write(b.getvalue())"
    ].join("\n"), fixture]);
    const imported = await teacher.page.request.post(`${webBase}${base}/tasks/${seeded.taskId}/h5p/import`, {
      headers: { origin: webBase }, multipart: { file: { name: "material.h5p", mimeType: "application/zip", buffer: archive } }
    });
    await expectApiOk(imported);
    registerE2EH5PContent(String((await imported.json()).h5p.content_id), teacherEmail);

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
    const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const outline = workbench.getByRole("complementary", { name: "Inhalt" });
    const exercise = workbench.getByRole("main", { name: "Bearbeitung" });
    const reader = workbench.getByRole("region", { name: "Dokument groß lesen" });
    await expect(exercise.locator(".h5p-multichoice")).toBeVisible({ timeout: 30_000 });
    const answer = exercise.getByRole("radio", { name: /Drei/ });
    await answer.press("Space");
    await expect(answer).toBeChecked();
    const player = await exercise.locator("h5p-player").evaluateHandle((node) => node);
    const instance = await player.evaluateHandle((node) => (node as HTMLElement & { h5pInstance: unknown }).h5pInstance);
    expect(await instance.evaluate((value) => Boolean(value))).toBe(true);
    const first = outline.getByRole("button", { name: "Nachschlagen 1 Material", exact: true });
    const last = outline.getByRole("button", { name: "Nachschlagen 2 Material", exact: true });
    await expect(first).toHaveAttribute("aria-expanded", "false");
    await expect(last).toHaveAttribute("aria-expanded", "false");
    for (const toggle of [first, last]) await toggle.click();
    for (const nr of [1, 2]) await expect(outline.getByText(`Vollständiger Begleittext ${nr}.`)).toBeVisible();
    await expect(reader).toHaveCount(0);
    await expect(exercise).toBeVisible();
    await expect(answer).toBeChecked();
    await learner.page.screenshot({ path: info.outputPath("h5p-material-tablet.png"), fullPage: true });
    await first.click();
    await expect(outline.getByText("Vollständiger Begleittext 1.")).toHaveCount(0);
    await expect(last).toHaveAttribute("aria-expanded", "true");
    await first.click();
    await outline.getByRole("button", { name: "Nachschlagen 1 groß lesen", exact: true }).click();
    await expect(reader).toContainText("Vollständiger Begleittext 1.");
    await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    await expect(answer).toBeChecked();

    await learner.page.setViewportSize({ width: 390, height: 844 });
    await workbench.getByRole("button", { name: "Materialien", exact: true }).click();
    await expect(outline.getByText("Vollständiger Begleittext 1.")).toBeVisible();
    await first.click();
    await expectNoViewportOverflow(learner.page);
    await learner.page.screenshot({ path: info.outputPath("h5p-material-mobile.png"), fullPage: true });
    await workbench.getByRole("button", { name: "Aufgabe", exact: true }).click();
    await expect(answer).toBeChecked();
    const nextAnswer = exercise.getByRole("radio", { name: /Vier/ });
    await nextAnswer.press("Space");
    await expect(nextAnswer).toBeChecked();
    expect(await player.evaluate((node, original) => node.isConnected && (node as HTMLElement & { h5pInstance: unknown }).h5pInstance === original, instance)).toBe(true);
    await player.dispose();
    await instance.dispose();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
