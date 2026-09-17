import { expect, test, type Browser, type Page } from "./support/feature-test";
import { newBrowserContext } from "./support/browser-context";
import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse, seedLearnerVisualSmokeCourse } from "./support/seed-data";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { completeQueuedFeedbackDeterministically, holdProviderWorker, releaseProviderWorker } from "./support/submission-finalization-fixture";
import { readFileSync } from "node:fs";

const answer = "Die Eingabe kommt vom Taster. Die Steuerung verarbeitet das Signal und schaltet die Fußgängerampel auf Grün. Das Licht ist die Ausgabe.\n\nDrücke ich den Taster, wird die Anforderung gespeichert. Die Steuerung prüft, wann die Autos anhalten müssen. Erst danach dürfen die Fußgänger die Straße überqueren.\n\nDer Taster ist also die Eingabe, die Steuerung übernimmt die Verarbeitung und die Ampelleuchten bilden die Ausgabe.".replaceAll("\n\n", " ");

async function setup(browser: Browser) {
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacher = await newBrowserContext(browser, { baseURL: webBase });
  const learner = await newBrowserContext(browser, { baseURL: webBase });
  const teacherPage = await teacher.newPage();
  const page = await learner.newPage();
  await login(teacherPage, teacherEmail, e2ePassword);
  await login(page, learnerEmail, e2ePassword);
  const seeded = await seedLearnerNavigationCourse(teacherPage, page, "Digitale Systeme");
  return { teacher, learner, teacherPage, page, seeded };
}

async function review(page: Page, seeded: { courseId: string; taskId: string }, text: string) {
  const learnerSub = await currentUserSub(page);
  const editor = page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
  await editor.fill(text);
  await holdProviderWorker();
  try {
    await page.getByRole("button", { name: /^(Neue )?Rückmeldung einholen$/ }).click();
    await expect(page.locator(".learning-task-feedback-status:visible")).toContainText("Rückmeldung wird erstellt");
    await completeQueuedFeedbackDeterministically({ ...seeded, learnerSub });
    await expect(page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
  } finally {
    await releaseProviderWorker();
  }
}

test("@feature-acceptance reads the final answer and nested feedback directly in the module", async ({ browser }, testInfo) => {
  test.setTimeout(150_000);
  const { teacher, learner, page, seeded } = await setup(browser);
  try {
    await page.goto(`/learning/courses/${seeded.courseId}`);
    await page.getByRole("link", { name: seeded.unitTitle }).click();
    await page.getByRole("button", { name: /Grundlagen/ }).click();
    await page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await review(page, seeded, answer);
    await page.getByRole("button", { name: "Endgültig abgeben" }).click();
    await expect(page.getByRole("region", { name: "Aufgabe abgeschlossen" })).toBeVisible();
    await page.getByRole("button", { name: /Zurück zum Modul/ }).click();
    const moduleUrl = page.url();
    await page.locator(`#task-row-${seeded.taskId}`).scrollIntoViewIfNeeded();
    const preview = page.getByRole("region", { name: "Eigene Abgabe zu Aufgabe 1", exact: true });
    await expect(preview).toBeVisible();
    await expect(preview).toContainText("Die Eingabe kommt vom Taster.");
    await expect(preview.getByText("Rückmeldung", { exact: true })).toHaveCount(0);
    // Capture the persisted reading view after the one-time completion notice.
    await page.reload();
    await page.locator(`#task-row-${seeded.taskId}`).scrollIntoViewIfNeeded();
    await expect(preview).toContainText("Die Eingabe kommt vom Taster.");
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    await page.locator(".learner-task-reading").first().evaluate((node) => node.scrollIntoView({ block: "center" }));
    await page.locator(".learner-task-reading").first().screenshot({ path: testInfo.outputPath("submission-collapsed.png") });
    const clipping = await preview.locator(".learning-submission-preview__text").evaluate((node) => ({
      height: node.clientHeight, full: node.scrollHeight, line: parseFloat(getComputedStyle(node).lineHeight)
    }));
    expect(clipping.height).toBeLessThanOrEqual(clipping.line * 3 + 1);
    expect(clipping.full).toBeGreaterThan(clipping.height);

    const toggle = preview.getByRole("button", { name: "Ausklappen" });
    await toggle.focus();
    await page.keyboard.press("Enter");
    await expect(preview.locator(".markdown-prose").first()).toContainText("Der Taster ist also die Eingabe");
    const feedback = preview.locator("details").filter({ has: page.locator("summary", { hasText: /^Rückmeldung$/ }) }).first();
    const evaluation = preview.locator(".learning-criteria-details");
    await expect(feedback).not.toHaveAttribute("open");
    await expect(evaluation).not.toHaveAttribute("open");
    await preview.getByText("Meine Abgabe", { exact: true }).click();
    await page.locator(".learner-task-reading").first().evaluate((node) => node.scrollIntoView({ block: "center" }));
    await page.locator(".learner-task-reading").first().screenshot({ path: testInfo.outputPath("submission-expanded.png") });
    await feedback.locator("summary").click();
    await expect(feedback).toHaveAttribute("open");
    await expect(evaluation).not.toHaveAttribute("open");
    await evaluation.locator("summary").first().click();
    await expect(evaluation).toHaveAttribute("open");
    const collapse = preview.getByRole("button", { name: "Einklappen" });
    await collapse.focus();
    await page.keyboard.press("Enter");
    await expect(preview.getByRole("button", { name: "Ausklappen" })).toBeFocused();
    await expect(preview.locator("details")).toHaveCount(0);
    expect(page.url()).toBe(moduleUrl);
    await page.reload();
    await page.locator(`#task-row-${seeded.taskId}`).scrollIntoViewIfNeeded();
    await expect(preview.getByRole("button", { name: "Ausklappen" })).toBeVisible();
  } finally { await learner.close(); await teacher.close(); }
});

for (const mime of ["image/png", "application/pdf"]) {
test(`@feature-detail linear sections preserve first and last answers with ${mime} uploads`, async ({ browser }, testInfo) => {
  test.setTimeout(150_000);
  const { teacher, learner, teacherPage, page } = await setup(browser);
  try {
    const linear = await seedLearnerVisualSmokeCourse(teacherPage, page, `Lineare Vorschau ${Date.now()}`);
    await page.goto(`/learning/courses/${linear.courseId}/units/${linear.unitId}`);
    const last = page.getByRole("region", { name: "Eigene Abgabe zu Aufgabe 2", exact: true });
    await page.getByRole("button", { name: "Erneut bearbeiten", exact: true }).scrollIntoViewIfNeeded();
    await expect(last).toContainText(linear.previousSubmissionText);
    await page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await review(page, linear, "Meine eigene Einordnung am Anfang des Abschnitts.");
    await page.locator("#learner-task-back").click();
    await page.locator(`#task-row-${linear.taskId}`).scrollIntoViewIfNeeded();
    const first = page.getByRole("region", { name: "Eigene Abgabe zu Aufgabe 1", exact: true });
    await expect(first).toContainText("Meine eigene Einordnung");
    // Measure the saved reading view, without the transient feedback notice.
    await page.reload();
    await page.locator(`#task-row-${linear.taskId}`).scrollIntoViewIfNeeded();
    await expect(first).toContainText("Meine eigene Einordnung");
    expect((await first.boundingBox())!.height).toBeLessThanOrEqual(112);
    const taskBounds = await page.locator(`#task-row-${linear.taskId} .learning-task-row`).boundingBox();
    expect((await first.boundingBox())!.y - taskBounds!.y - taskBounds!.height).toBeLessThanOrEqual(16);
    const instructionSize = await page.locator(`#task-row-${linear.taskId} .learning-task-row__preview`).evaluate((node) => parseFloat(getComputedStyle(node).fontSize));
    expect(instructionSize).toBeGreaterThanOrEqual(16);
    await page.locator(".learner-task-reading").first().screenshot({ path: testInfo.outputPath("short-answer.png") });
    await page.getByRole("button", { name: "Entwurf weiterbearbeiten" }).click();
    const editor = page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await editor.fill("Mein lokaler Text bleibt im Editor.");
    await page.locator("#learner-task-back").click();
    await expect(first).not.toContainText("Mein lokaler Text");
    await page.getByRole("button", { name: "Entwurf weiterbearbeiten" }).click();
    await expect(editor).toContainText("Mein lokaler Text bleibt im Editor.");

    await page.getByRole("radio", { name: "Datei hochladen", exact: true }).focus();
    await page.keyboard.press("Space");
    await page.getByLabel("Datei auswählen").setInputFiles({
      name: mime === "image/png" ? "abgabe.png" : "abgabe.pdf", mimeType: mime,
      buffer: mime === "image/png"
        ? Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AARAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg==", "base64")
        : readFileSync(new URL("./fixtures/submission-preview.pdf", import.meta.url))
    });
    const learnerSub = await currentUserSub(page);
    await holdProviderWorker();
    try {
      await page.getByRole("button", { name: /^(Neue )?Rückmeldung einholen$/ }).click();
      await expect(page.locator(".learning-task-feedback-status:visible")).toContainText("Rückmeldung wird erstellt");
      await completeQueuedFeedbackDeterministically({ courseId: linear.courseId, taskId: linear.taskId, learnerSub });
      await expect(page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
    } finally { await releaseProviderWorker(); }
    await page.locator("#learner-task-back").click();
    await page.locator(`#task-row-${linear.taskId}`).scrollIntoViewIfNeeded();
    if (mime === "image/png") {
      const image = first.getByRole("img");
      await expect(image).toBeVisible();
      await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    } else {
      await expect(first).toContainText("PDF");
      await expect(first.locator("iframe")).toHaveCount(0);
    }
    await first.getByRole("button", { name: "Ausklappen" }).click();
    if (mime === "application/pdf") await expect(first.getByTitle("Abgabe zu Aufgabe 1")).toBeVisible();
    const href = await first.getByRole("link", { name: "Datei öffnen" }).getAttribute("href");
    expect(href).toContain(`/tasks/${linear.taskId}/submissions/`);
    const file = await page.request.get(href!);
    expect(file.status()).toBe(200);
    expect(file.headers()["content-type"]).toContain(mime);
    await expect(last).toContainText(linear.previousSubmissionText);
  } finally { await learner.close(); await teacher.close(); }
});
}

test("@feature-detail saved drafts, final priority and responsive reading preserve editing", async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const { teacher, learner, page, seeded } = await setup(browser);
  try {
    const url = `/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}`;
    await page.goto(url);
    await expect(page.locator(".learning-submission-preview")).toHaveCount(0);
    await page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await review(page, seeded, answer);
    await page.locator("#learner-task-back").click();
    await page.locator(`#task-row-${seeded.taskId}`).scrollIntoViewIfNeeded();
    const preview = page.getByRole("region", { name: "Eigene Abgabe zu Aufgabe 1", exact: true });
    await expect(preview.getByText("Mein Entwurf", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Entwurf weiterbearbeiten" }).click();
    await page.getByRole("button", { name: "Endgültig abgeben" }).click();
    await expect(page.getByRole("region", { name: "Aufgabe abgeschlossen" })).toBeVisible();
    await page.getByRole("button", { name: /Zurück zum Modul/ }).click();
    await page.getByRole("button", { name: "Erneut bearbeiten", exact: true }).click();
    await review(page, seeded, "Ein neuerer gespeicherter Entwurf.");
    await page.locator("#learner-task-back").click();
    await page.locator(`#task-row-${seeded.taskId}`).scrollIntoViewIfNeeded();
    await expect(preview).toContainText("Die Eingabe kommt vom Taster.");
    await expect(page.getByText("Neuerer Entwurf vorhanden", { exact: true })).toBeVisible();
    await page.reload();
    await page.locator(`#task-row-${seeded.taskId}`).scrollIntoViewIfNeeded();
    await expect(preview).toContainText("Die Eingabe kommt vom Taster.");
    await expect(page.getByText("Neuerer Entwurf vorhanden", { exact: true })).toBeVisible();
    for (const [width, height] of [[1920, 1080], [1024, 768], [390, 844]]) {
      await page.setViewportSize({ width, height });
      for (const theme of ["light", "dark"]) {
        await page.evaluate((theme) => document.documentElement.setAttribute("data-theme", theme), theme);
        await page.screenshot({ path: testInfo.outputPath(`preview-${width}-${theme}-collapsed.png`), fullPage: true });
        await page.locator(".learner-task-reading").first().screenshot({ path: testInfo.outputPath(`answer-${width}-${theme}-collapsed.png`) });
        await expectNoViewportOverflow(page);
        const readingSurface = await page.locator(".learner-task-reading").first().evaluate((node) => getComputedStyle(node).backgroundColor);
        expect(readingSurface).not.toBe("rgba(0, 0, 0, 0)");
        if (width >= 1024) {
          const editBounds = await page.locator(`#task-row-${seeded.taskId}`).getByRole("button", { name: "Erneut bearbeiten", exact: true }).boundingBox();
          const expandBounds = await preview.getByRole("button", { name: "Ausklappen" }).boundingBox();
          expect(Math.abs(editBounds!.x + editBounds!.width - expandBounds!.x - expandBounds!.width)).toBeLessThanOrEqual(2);
        }
        const expand = preview.getByRole("button", { name: "Ausklappen" });
        await expect(expand).toBeVisible();
        expect((await expand.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        await expand.click();
        await expect(preview.getByText("Auswertung", { exact: true })).toBeVisible();
        const disclosureMetrics = await preview.locator(".learning-submission-preview__details > details > summary").evaluateAll((nodes) => nodes.map((node) => ({
          height: node.getBoundingClientRect().height, font: getComputedStyle(node).font
        })));
        expect(disclosureMetrics).toHaveLength(2);
        expect(disclosureMetrics[0].font).toBe(disclosureMetrics[1].font);
        expect(disclosureMetrics.every((metric) => metric.height >= 44)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath(`preview-${width}-${theme}.png`), fullPage: true });
        await page.locator(".learner-task-reading").first().screenshot({ path: testInfo.outputPath(`answer-${width}-${theme}.png`) });
        await preview.getByRole("button", { name: "Einklappen" }).click();
      }
    }
    await page.getByRole("button", { name: "Entwurf weiterbearbeiten" }).click();
    await expect(page.locator('.learning-markdown-editor__surface [contenteditable="true"]')).toContainText("Ein neuerer gespeicherter Entwurf.");
    await page.locator("#learner-task-back").click();
    await page.getByRole("button", { name: "Aufgabe 2 beginnen" }).click();
    await page.locator('.learning-markdown-editor__surface [contenteditable="true"]').fill("Lokaler Entwurf zur letzten Modulaufgabe.");
    await page.locator("#learner-task-back").click();
    await expect(preview).toContainText("Die Eingabe kommt vom Taster.");
    await expect(page.getByRole("region", { name: "Eigene Abgabe zu Aufgabe 2", exact: true })).toHaveCount(0);
    await page.locator(`#task-row-${seeded.secondTaskId}`).getByRole("button").click();
    await expect(page.locator('.learning-markdown-editor__surface [contenteditable="true"]')).toContainText("Lokaler Entwurf zur letzten Modulaufgabe.");
  } finally { await learner.close(); await teacher.close(); }
});
