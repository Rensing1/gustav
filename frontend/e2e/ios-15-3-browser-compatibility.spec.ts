import { installBrowserCompatibilityProfile } from "./support/ios-15-3-profile";
import { openAppDestination } from "./support/app-navigation";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { newBrowserContext } from "./support/browser-context";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedH5pVisualSmokeUnit, seedLearnerDialogCourse, seedLearnerNavigationCourse, seedLearnerPracticeCourse } from "./support/seed-data";
import { findCascadeLayers } from "../tooling/css-compatibility.mjs";
import { apiHeaders } from "./support/api";
import { devices } from "@playwright/test";
import { completeQueuedFeedbackDeterministically, holdProviderWorker, releaseProviderWorker } from "./support/submission-finalization-fixture";

const password = e2ePassword;

type Profile = "camera" | "combined" | "modern";

async function authenticatedPage(browser: Browser, profile: Profile = "combined"): Promise<{ context: BrowserContext; page: Page }> {
  const context = await newBrowserContext(browser, { ...devices["iPad Pro 11 landscape"], baseURL: webBase, locale: "de-DE" });
  await installBrowserCompatibilityProfile(context, profile);
  return { context, page: await context.newPage() };
}

async function expectCompatibleStylesheets(page: Page): Promise<void> {
  const stylesheetUrls = await page.locator('link[rel="stylesheet"]').evaluateAll((links) =>
    links.map((link) => (link as HTMLLinkElement).href)
  );
  expect(stylesheetUrls.length).toBeGreaterThan(0);

  for (const stylesheetUrl of stylesheetUrls) {
    const response = await page.request.get(stylesheetUrl);
    expect(response.ok(), `Stylesheet could not be loaded: ${stylesheetUrl}`).toBe(true);
    const layers = findCascadeLayers(await response.text(), stylesheetUrl);
    expect(layers, `Cascade layer remained in: ${stylesheetUrl}`).toEqual([]);
  }
}

for (const profile of ["camera", "combined", "modern"] as const) {
  test(`@feature-acceptance opens and navigates a visible graph (${profile})`, async ({ browser }) => {
    test.setTimeout(90_000);
    const unique = Date.now();
    const teacherEmail = e2eEmail("teacher");
    const learnerEmail = e2eEmail("learner");
    await ensureTeacherUser(teacherEmail, password);
    await ensureLearnerUser(learnerEmail, password);

    const teacher = await authenticatedPage(browser, profile);
    const learner = await authenticatedPage(browser, profile);
    try {
      await login(teacher.page, teacherEmail, password);
      await login(learner.page, learnerEmail, password);
      const seeded = await seedLearnerNavigationCourse(
        teacher.page,
        learner.page,
        `iPad-CSS-Kompatibilität ${unique}`
      );
      const edgeResponse = await teacher.page.request.post(`${webBase}/api/teaching/units/${seeded.unitId}/modules/edges`, {
        headers: apiHeaders(`/teaching/units/${seeded.unitId}`),
        data: { from_module_id: seeded.graphModuleId, to_module_id: seeded.contextGraphModuleId }
      });
      expect(edgeResponse.ok()).toBe(true);

      await learner.page.setViewportSize({ width: 1280, height: 900 });
      const errors = trackErrors(learner.page);
      await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await expect(learner.page.locator(".workspace-page")).toBeVisible();

      await learner.page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
      const module = learner.page.getByRole("button", { name: /Grundlagen/ });
      await expect(module).toBeInViewport();
      const edge = learner.page.locator(".svelte-flow__edge-path").first();
      // A horizontal SVG path has zero box height but still paints a visible stroke.
      await expect.poll(() => edge.evaluate((path: SVGPathElement) => {
        const box = path.getBoundingClientRect();
        const graph = document.querySelector(".svelte-flow")!.getBoundingClientRect();
        const style = getComputedStyle(path);
        return path.getTotalLength() > 0 && style.stroke !== "none" && parseFloat(style.strokeWidth) > 0
          && box.right > graph.left && box.left < graph.right && box.bottom >= graph.top && box.top <= graph.bottom;
      })).toBe(true);
      expect(errors).toEqual([]);
      if (profile === "camera") {
        await learner.page.evaluate(() => {
          const constructor = Promise as unknown as { withResolvers: unknown };
          const original = constructor.withResolvers;
          (window as unknown as { restoreResolvers: () => void }).restoreResolvers = () => { constructor.withResolvers = original; };
          constructor.withResolvers = undefined;
        });
        await learner.page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
        await expect(learner.page.getByRole("alert")).toHaveText("Die Graphansicht konnte nicht ausgerichtet werden. Bitte versuche es erneut.");
        await learner.page.evaluate(() => (window as unknown as { restoreResolvers: () => void }).restoreResolvers());
        await learner.page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
        await expect(learner.page.getByRole("alert")).toBeHidden();
      }

      await expectCompatibleStylesheets(learner.page);
      const layout = await learner.page.evaluate(() => ({
        shellDisplay: getComputedStyle(document.querySelector(".app-shell")!).display,
        topbarPosition: getComputedStyle(document.querySelector(".global-header")!).position,
        workspaceDisplay: getComputedStyle(document.querySelector(".workspace-page")!).display,
        graphMinHeightRem:
          parseFloat(getComputedStyle(document.querySelector(".graph-stage-frame .teacher-flow-shell")!).minHeight) /
          parseFloat(getComputedStyle(document.documentElement).fontSize),
        graphBackgroundImage: getComputedStyle(
          document.querySelector(".graph-stage-frame .teacher-flow-shell")!
        ).backgroundImage
      }));
      expect(layout.graphMinHeightRem).toBeGreaterThan(0);
      expect(layout).toMatchObject({
        shellDisplay: "block",
        topbarPosition: "sticky",
        workspaceDisplay: "grid",
        graphBackgroundImage: "none"
      });
      const camera = await learner.page.locator(".svelte-flow__viewport").getAttribute("style");
      await learner.page.reload();
      await expect(learner.page.locator(".svelte-flow__viewport")).toHaveAttribute("style", camera!);
      await learner.page.evaluate((id) => sessionStorage.setItem(`gustav:learner-graph:${id}:viewport`, JSON.stringify({ x: 100_000, y: 100_000, zoom: 0.8 })), seeded.unitId);
      await learner.page.reload();
      await expect(module).not.toBeInViewport();
      await learner.page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
      await expect(module).toBeInViewport();
      await learner.page.setViewportSize({ width: 768, height: 1024 });
      await expect(learner.page.getByRole("navigation", { name: "Lernpfad nach Phasen" })).toBeVisible();
      await expect(module).toBeInViewport();
      await module.click();
      await expect(learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" })).toBeVisible();
      // Exercise client navigation back to the graph as well as direct entry.
      await learner.page.locator(".context-header__back").click();
      await expect(learner.page.getByRole("navigation", { name: "Lernpfad nach Phasen" })).toBeVisible();
      await learner.page.setViewportSize({ width: 1024, height: 768 });
      const mobilePath = learner.page.getByRole("navigation", { name: "Lernpfad nach Phasen" });
      await expect(mobilePath).toBeVisible();
      await expect(mobilePath.getByRole("button", { name: /Modul öffnen.*Grundlagen/ })).toBeVisible();
      await expect(mobilePath.getByRole("link", { name: "Quellen", exact: true })).toBeVisible();
      expect(errors).toEqual([]);
    } finally {
      await learner.context.close();
      await teacher.context.close();
    }
  });
}

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

async function roles(browser: Browser, profile: Profile) {
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  const teacher = await authenticatedPage(browser, profile);
  const learner = await authenticatedPage(browser, profile);
  await login(teacher.page, teacherEmail, password);
  await login(learner.page, learnerEmail, password);
  return { teacher, learner };
}

for (const profile of ["combined", "modern"] as const) {
  test(`@feature-detail preserves H5P answers through fullscreen (${profile})`, async ({ browser }, info) => {
    test.setTimeout(150_000);
    const { teacher, learner } = await roles(browser, profile);
    const page = learner.page;
    const errors = trackErrors(page);
    try {
      const seeded = await seedH5pVisualSmokeUnit(teacher.page, page, `iPad-H5P ${Date.now()}`);
      const root = resolve(process.cwd(), "..");
      const pkg = execFileSync(resolve(root, ".venv/bin/python"), ["-c", [
        "import io, pathlib, sys, zipfile", "buffer = io.BytesIO()",
        "with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:",
        "    for path in pathlib.Path(sys.argv[1]).rglob('*'):",
        "        if path.is_file(): archive.write(path, path.relative_to(sys.argv[1]))",
        "sys.stdout.buffer.write(buffer.getvalue())"
      ].join("\n"), resolve(root, "frontend/e2e/fixtures/h5p-multichoice-design")]);
      const imported = await teacher.page.request.post(`${webBase}/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}/tasks/${seeded.taskId}/h5p/import`, {
        headers: { origin: webBase }, multipart: { file: { name: "compatibility.h5p", mimeType: "application/zip", buffer: pkg } }
      });
      expect(imported.ok()).toBe(true);
      registerE2EH5PContent(String((await imported.json()).h5p.content_id), e2eEmail("teacher"));
      await page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await page.getByRole("button", { name: /beginnen/ }).first().click();
      await expect(page.locator(".h5p-multichoice")).toBeVisible();
      const player = await page.locator("h5p-player").elementHandle();
      const answer = page.getByRole("radio", { name: /Vier/ });
      await answer.press("Space");
      const opener = page.getByRole("button", { name: "Vollbild", exact: true });
      const host = page.locator(".h5p-fullscreen-host");
      for (const closeWith of ["Escape", "button"] as const) {
        if (closeWith === "button") {
          await page.setViewportSize({ width: 768, height: 1024 });
          await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
        }
        await opener.click();
        await expect(host).toHaveAttribute("aria-modal", "true");
        const exit = page.getByRole("button", { name: "Vollbild verlassen", exact: true });
        await expect(exit).toBeFocused();
        await expect(host).toHaveCSS("position", "fixed");
        const box = (await host.boundingBox())!;
        expect(Math.abs(box.x)).toBeLessThanOrEqual(1);
        expect(Math.abs(box.y)).toBeLessThanOrEqual(1);
        expect(Math.abs(box.width - page.viewportSize()!.width)).toBeLessThanOrEqual(1);
        expect(Math.abs(box.height - page.viewportSize()!.height)).toBeLessThanOrEqual(1);
        await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
        // The global header is outside the modal even when native inert is missing.
        await expect.poll(() => page.locator(".global-header").evaluate((node) => Boolean(node.closest('[aria-hidden="true"]')))).toBe(true);
        await page.keyboard.press("Shift+Tab");
        expect(await host.evaluate((node) => node.contains(document.activeElement))).toBe(true);
        await page.screenshot({ path: info.outputPath(`h5p-fullscreen-${closeWith}.png`) });
        if (closeWith === "Escape") await page.keyboard.press("Escape");
        else await exit.click();
        await expect(host).not.toHaveAttribute("aria-modal", "true");
        await expect(opener).toBeFocused();
        await expect(answer).toHaveAttribute("aria-checked", "true");
        expect(await player!.evaluate((node) => node === document.querySelector("h5p-player"))).toBe(true);
        await expect.poll(() => page.locator(".global-header").evaluate((node) => Boolean(node.closest('[aria-hidden="true"]')))).toBe(false);
        await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");
      }
      await page.getByRole("button", { name: /Check|Die Antworten überprüfen/ }).click();
      await expect(page.getByText("Gespeichert (1/1).")).toBeVisible();
      await expect(page.locator(".h5p-multichoice")).toBeVisible();
      const saved = await page.request.get(`${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions`);
      expect(saved.ok()).toBe(true);
      expect(await saved.json()).toEqual(expect.arrayContaining([
        expect.objectContaining({ kind: "h5p", score_raw: 1, score_max: 1 })
      ]));
      expect(errors).toEqual([]);
    } finally { await learner.context.close(); await teacher.context.close(); }
  });

  test(`@feature-detail requests feedback for text after a reviewed image (${profile})`, async ({ browser }) => {
    test.setTimeout(150_000);
    const { teacher, learner } = await roles(browser, profile);
    const page = learner.page;
    const errors = trackErrors(page);
    try {
      const seeded = await seedLearnerNavigationCourse(teacher.page, page, `iPad-Antwortwechsel ${Date.now()}`);
      const learnerSub = await currentUserSub(page);
      await page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}`);
      await page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
      await page.getByRole("radio", { name: "Datei hochladen", exact: true }).press("Space");
      await page.getByLabel("Datei auswählen").setInputFiles({ name: "antwort.png", mimeType: "image/png",
        buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AARAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg==", "base64") });
      await holdProviderWorker();
      try {
        await page.getByRole("button", { name: "Rückmeldung einholen", exact: true }).click();
        await expect(page.locator(".learning-task-feedback-status:visible")).toContainText("Rückmeldung wird erstellt");
        await completeQueuedFeedbackDeterministically({ ...seeded, learnerSub });
        await expect(page.getByRole("button", { name: "Abgeben", exact: true })).toBeEnabled();
        await page.getByRole("radio", { name: "Text schreiben", exact: true }).press("Space");
        await page.locator('.learning-markdown-editor__surface [contenteditable="true"]').fill("Meine neue schriftliche Begründung.");
        await page.getByRole("button", { name: "Neue Rückmeldung einholen", exact: true }).click();
        await expect(page.locator(".learning-task-feedback-status:visible")).toContainText("Rückmeldung wird erstellt");
        await completeQueuedFeedbackDeterministically({ ...seeded, learnerSub });
        await expect(page.getByRole("button", { name: "Abgeben", exact: true })).toBeEnabled();
      } finally { await releaseProviderWorker(); }
      const response = await page.request.get(`${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions`);
      expect(response.ok()).toBe(true);
      const submissions = await response.json();
      expect(submissions).toEqual(expect.arrayContaining([
        expect.objectContaining({ kind: "image", analysis_status: "completed" }),
        expect.objectContaining({ kind: "text", text_body: "Meine neue schriftliche Begründung.", analysis_status: "completed" })
      ]));
      expect(errors).toEqual([]);
    } finally { await learner.context.close(); await teacher.context.close(); }
  });

  test(`@feature-detail finalizes reviewed text exactly once (${profile})`, async ({ browser }) => {
    test.setTimeout(120_000);
    const { teacher, learner } = await roles(browser, profile);
    const errors = trackErrors(learner.page);
    try {
      const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `iPad-Abgabe ${Date.now()}`);
      const learnerSub = await currentUserSub(learner.page);
      await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
      await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
      const editor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
      await editor.fill("Dieser Entwurf begründet die Position mit einem Beleg.");
      await holdProviderWorker();
      try {
        await learner.page.getByRole("button", { name: "Rückmeldung einholen", exact: true }).click();
        await expect(learner.page.locator(".learning-task-feedback-status:visible").getByText("Rückmeldung wird erstellt ...", { exact: true })).toBeVisible();
        await completeQueuedFeedbackDeterministically({ courseId: seeded.courseId, taskId: seeded.taskId, learnerSub });
      } finally { await releaseProviderWorker(); }
      const final = learner.page.getByRole("button", { name: "Abgeben", exact: true });
      await expect(final).toBeEnabled();
      await editor.fill("Diese weitere Überarbeitung ist noch nicht geprüft.");
      await final.click();
      const warning = learner.page.getByRole("dialog", { name: "Überarbeitung noch nicht geprüft" });
      await expect(warning.getByRole("button", { name: "Weiter überarbeiten" })).toBeFocused();
      await learner.page.keyboard.press("Escape");
      await expect(warning).toBeHidden();
      await expect(final).toBeFocused();
      await final.click();
      await warning.getByRole("button", { name: "Weiter überarbeiten" }).click();
      await expect(editor).toBeFocused();
      let requests = 0;
      learner.page.on("request", (request) => {
        if (request.method() === "POST" && new URL(request.url()).pathname.endsWith(seeded.unitId)
          && new URLSearchParams(request.postData() ?? "").get("submission_intent") === "submit") requests += 1;
      });
      await final.click();
      await warning.getByRole("button", { name: "Trotzdem abgeben" }).click();
      await expect(learner.page.getByText("Aufgabe abgegeben.", { exact: true })).toBeVisible();
      expect(requests).toBe(1);
      expect(errors).toEqual([]);
    } finally { await learner.context.close(); await teacher.context.close(); }
  });

  test(`@feature-detail resumes and ends practice (${profile})`, async ({ browser }) => {
    const { teacher, learner } = await roles(browser, profile);
    const errors = trackErrors(learner.page);
    try {
      const seeded = await seedLearnerPracticeCourse(teacher.page, learner.page, `iPad-Üben ${Date.now()}`);
      await learner.page.goto(`/learning/practice?course_id=${seeded.courseId}&practice_module_id=${seeded.practiceModuleId}`);
      await learner.page.getByRole("button", { name: /Aufgabe.*starten/ }).click();
      const opener = learner.page.getByRole("button", { name: "Sitzung beenden", exact: true });
      await opener.click();
      const dialog = learner.page.getByRole("dialog", { name: "Möchtest du die Übung jetzt beenden?" });
      await expect(dialog.getByRole("button", { name: "Weiter üben" })).toBeFocused();
      await learner.page.keyboard.press("Shift+Tab");
      await expect(dialog.getByRole("button", { name: "Sitzung beenden" })).toBeFocused();
      await learner.page.keyboard.press("Escape");
      await expect(opener).toBeFocused();
      await opener.click();
      await dialog.getByRole("button", { name: "Weiter üben" }).click();
      await expect(dialog).toBeHidden();
      await opener.click();
      await dialog.getByRole("button", { name: "Sitzung beenden" }).click();
      await expect(learner.page).toHaveURL(/\/summary/);
      expect(errors).toEqual([]);
    } finally { await learner.context.close(); await teacher.context.close(); }
  });

  test(`@feature-detail sends an AI dialog answer with a secure UUID (${profile})`, async ({ browser }) => {
    const { teacher, learner } = await roles(browser, profile);
    const errors = trackErrors(learner.page);
    try {
      const seeded = await seedLearnerDialogCourse(teacher.page, learner.page, `iPad-Dialog ${Date.now()}`);
      await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
      await expect(learner.page.getByRole("region", { name: "KI-Dialog" })).toBeVisible();
      await expect(learner.page.getByText("Welche Beobachtung möchtest du zuerst untersuchen?")).toBeVisible();
      await holdProviderWorker();
      try {
        await learner.page.getByRole("textbox", { name: /Deine Antwort/ }).fill("Die Quelle zeigt eine konkrete Beobachtung.");
        const sent = learner.page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/turns"));
        await learner.page.getByRole("button", { name: "Antwort senden", exact: true }).click();
        const response = await sent;
        expect(response.ok()).toBe(true);
        expect(response.request().headers()["idempotency-key"]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
        await expect(learner.page.getByText("Die Quelle zeigt eine konkrete Beobachtung.", { exact: true })).toBeVisible();
      } finally { await releaseProviderWorker(); }
      expect(errors).toEqual([]);
    } finally { await learner.context.close(); await teacher.context.close(); }
  });

  test(`@feature-detail teacher uses graph, module editor, invitation and live matrix (${profile})`, async ({ browser }) => {
    test.setTimeout(90_000);
    const { teacher, learner } = await roles(browser, profile);
    const errors = trackErrors(teacher.page);
    try {
      const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `iPad-Lehrkraft ${Date.now()}`);
      await teacher.page.goto(`/teaching/units/${seeded.unitId}`);
      await teacher.page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
      await expect(teacher.page.locator(".svelte-flow__node").first()).toBeInViewport();
      await teacher.page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.graphModuleId}`);
      await expect(teacher.page.getByRole("heading", { name: "Grundlagen", exact: true })).toBeVisible();
      // Upload preparation re-submits without a submitter: exercise that fallback
      // through the real editor, storage and server action, not just the helper.
      await teacher.page.getByRole("button", { name: "Material hinzufügen", exact: true }).first().click();
      const materialForm = teacher.page.locator('form[action="?/createMaterial"]');
      await materialForm.getByLabel("Materialtyp").selectOption("simulation");
      await materialForm.getByLabel("Titel", { exact: true }).fill("iPad-Testmaterial");
      await materialForm.getByLabel("HTML-Simulation").setInputFiles({
        name: "ipad-testmaterial.html", mimeType: "text/html",
        buffer: Buffer.from('<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Testmaterial</title></head><body><p>Eigenständiges Testmaterial.</p></body></html>')
      });
      await materialForm.getByRole("button", { name: "Material hinzufügen", exact: true }).click();
      await expect(teacher.page.getByText("Material angelegt.", { exact: true })).toBeVisible();
      await openAppDestination(teacher.page, "Live");
      await teacher.page.getByRole("combobox", { name: "Kurs", exact: true }).selectOption(seeded.courseId);
      await teacher.page.getByRole("combobox", { name: "Lerneinheit", exact: true }).selectOption(seeded.unitId);
      const matrix = teacher.page.getByRole("region", { name: "Lernaufgaben nach Schülern" });
      await expect(matrix.locator("tbody tr")).toHaveCount(1);
      for (const size of [{ width: 1024, height: 768 }, { width: 768, height: 1024 }]) {
        await teacher.page.setViewportSize(size);
        await expect(matrix).toBeVisible();
        expect(await teacher.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      }
      // Native Chromium fullscreen prevents Playwright window resizing even
      // after document.exitFullscreen, so check orientation before fullscreen.
      await teacher.page.goto(`/teaching/courses/${seeded.courseId}`);
      await teacher.page.getByRole("button", { name: "Mitglieder verwalten" }).click();
      // The drawer opens optimistically; finish its route load before submitting.
      const invitationLoaded = teacher.page.waitForResponse((response) => response.url().includes("/__data.json?invite=1"));
      await teacher.page.getByRole("link", { name: "Klasse einladen" }).click();
      expect((await invitationLoaded).ok()).toBe(true);
      const drawer = teacher.page.getByRole("dialog", { name: "Klasse einladen" });
      await drawer.getByRole("button", { name: "Klassenlink erstellen" }).click();
      await expect(drawer.getByRole("textbox", { name: "Klassenlink" })).toBeVisible();
      if (profile === "combined") {
        await teacher.page.evaluate(() => Object.defineProperty(HTMLElement.prototype, "requestFullscreen", { value: undefined, configurable: true }));
      }
      await teacher.page.getByRole("button", { name: "Im Vollbild anzeigen" }).click();
      const fullscreen = teacher.page.getByRole("dialog", { name: "QR-Code im Vollbild" });
      await expect(fullscreen.locator("canvas")).toBeVisible();
      await teacher.page.keyboard.press("Escape");
      await expect(fullscreen).toBeHidden();
      // Native fullscreen exits asynchronously; wait before navigation/resizing.
      await expect.poll(() => teacher.page.evaluate(() => document.fullscreenElement === null)).toBe(true);
      await teacher.page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();
      expect(errors).toEqual([]);
    } finally { await learner.context.close(); await teacher.context.close(); }
  });
}
