import { readFileSync } from "node:fs";
import { devices } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { expect, test } from "./support/feature-test";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { apiHeaders, expectApiOk } from "./support/api";
import { seedLearnerNavigationCourse } from "./support/seed-data";
import { newBrowserContext } from "./support/browser-context";
import { setAppTheme } from "./support/app-navigation";
import { installBrowserCompatibilityProfile } from "./support/ios-15-3-profile";

const fixtures: Record<string, string> = JSON.parse(readFileSync(new URL("./fixtures/mermaid-diagrams.json", import.meta.url), "utf8"));

test("@feature-acceptance authors Mermaid through the editor, reopens, reads and prints it", async ({ browser }, info) => {
  test.setTimeout(240_000);
  const device = info.project.name === "webkit-ipad" ? devices["iPad Pro 11 landscape"] : {};
  const teacherContext = await newBrowserContext(browser, { ...device, baseURL: webBase });
  const learnerContext = await newBrowserContext(browser, { ...device, baseURL: webBase,
    viewport: info.project.name === "webkit-ipad" ? { width: 1194, height: 834 } : { width: 1920, height: 1080 } });
  const teacher = await teacherContext.newPage(), learner = await learnerContext.newPage();
  try {
    if (info.project.name === "webkit-ipad") await installBrowserCompatibilityProfile(learnerContext, "combined");
    await ensureTeacherUser(e2eEmail("teacher"), e2ePassword);
    await ensureLearnerUser(e2eEmail("learner"), e2ePassword);
    await login(teacher, e2eEmail("teacher"), e2ePassword);
    await login(learner, e2eEmail("learner"), e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, `Markdown ${Date.now()}`);
    const editorUrl = `/teaching/units/${seeded.unitId}/nodes/${seeded.graphModuleId}`;
    await teacher.goto(editorUrl);
    await teacher.getByRole("button", { name: /Grundrechte und digitale Kommunikation/ }).click();
    const form = teacher.locator('form[action="?/saveMaterial"]');
    const editor = form.locator('[contenteditable="true"]');
    await editor.click();
    // WebKit's platform shortcuts do not select the full ProseMirror document.
    // Select visible content only; all mutations still use real keyboard input.
    await editor.evaluate((element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
    });
    await editor.press("Backspace");
    await expect(form.locator('input[name="body_md"]')).toHaveValue("");
    await editor.pressSequentially("```mermaid ");
    await expect(editor.locator("pre")).toBeVisible();
    await editor.pressSequentially("sequenceDiagram");
    await editor.press("Enter");
    await editor.pressSequentially("    Alice->>Bob: Hallo");
    await editor.press("Enter");
    await editor.pressSequentially("    Bob-->>Alice: Antwort");
    // Modify the source through actual editor input immediately before saving.
    await editor.press("End");
    await editor.pressSequentially("!");
    const expected = "sequenceDiagram\n    Alice->>Bob: Hallo\n    Bob-->>Alice: Antwort!";
    await form.getByRole("button", { name: "Änderungen speichern", exact: true }).click();
    await teacher.goto("/teaching");
    await teacher.goto(editorUrl);
    await teacher.getByRole("button", { name: /Grundrechte und digitale Kommunikation/ }).click();
    expect(await form.locator("pre code").textContent()).toBe(expected);
    expect((await form.locator('input[name="body_md"]').inputValue()).trimEnd()).toBe(`\`\`\`mermaid\n${expected}\n\`\`\``);

    const browserErrors: string[] = [];
    learner.on("pageerror", (error) => browserErrors.push(error.message));
    learner.on("console", (message) => { if (message.type() === "error") browserErrors.push(message.text().slice(0, 300)); });
    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.screenshot({ path: info.outputPath("learner-graph.png"), fullPage: true });
    await expect(learner.getByRole("button", { name: /Grundlagen/ }), JSON.stringify(browserErrors)).toBeVisible();
    await learner.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.locator(`#task-row-${seeded.taskId}`).getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const materialsTab = learner.getByRole("button", { name: "Materialien", exact: true });
    if (await materialsTab.isVisible()) await materialsTab.click();
    const materialToggle = learner.getByRole("button", { name: "Grundrechte und digitale Kommunikation Material", exact: true });
    if (await materialToggle.getAttribute("aria-expanded") !== "true") await materialToggle.click();
    await learner.screenshot({ path: info.outputPath("material-open.png"), fullPage: true });
    const diagram = learner.locator(".markdown-diagram:visible").first();
    await expect(diagram.locator("img")).toBeVisible({ timeout: 30_000 });
    await diagram.getByText("Quelltext anzeigen", { exact: true }).click();
    await expect(diagram.locator("pre")).toHaveText(expected + "\n");
    for (const theme of ["light", "dark"] as const) {
      await setAppTheme(learner, theme);
      await learner.setViewportSize({ width: 1024, height: 768 });
      if (await materialsTab.isVisible()) await materialsTab.click();
      await expect(diagram.locator("img")).toBeVisible();
      await expect.poll(() => learner.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await learner.screenshot({ path: info.outputPath(`mermaid-${theme}.png`), fullPage: true });
    }
    // All native types share this renderer; keep the UI journey focused on editing.
    const batch = await teacher.request.post("/api/markdown/diagrams", {
      headers: apiHeaders(), data: { sources: Object.values(fixtures), theme: "light" }
    });
    await expectApiOk(batch);
    const renderedTypes = (await batch.json()).diagrams;
    for (const [index, name] of Object.keys(fixtures).entries()) {
      expect(renderedTypes[index].png, name).toBeTruthy();
    }
    const gallerySource = "# Mermaid-Typen\n\n```mermaid\nflowchart LR\nA[Start] --> B[Ziel]\n```\n\n```mermaid\nnot-a-diagram\n```\n\n```html\n<div>Beispiel</div>\n\t<script>window.__markdownExecution = true</script>\n```";
    await expectApiOk(await teacher.request.patch(`/api/teaching/units/${seeded.unitId}/modules/${seeded.graphModuleId}/tasks/${seeded.taskId}`, {
      headers: apiHeaders(), data: { instruction_md: gallerySource }
    }));
    await learner.reload();
    const start = learner.getByRole("button", { name: /beginnen/i }).first();
    if (await start.isVisible()) await start.click();
    const taskTab = learner.getByRole("button", { name: "Aufgabe", exact: true });
    if (await taskTab.isVisible()) await taskTab.click();
    const gallery = learner.locator(".markdown-prose").filter({ hasText: "Mermaid-Typen" }).first();
    await expect(gallery).toBeAttached();
    await expect(gallery.locator(".markdown-diagram").nth(0).locator("img")).toBeVisible({ timeout: 30_000 });
    await expect(gallery.locator(".markdown-diagram").nth(1).getByRole("status")).toContainText("Das Diagramm konnte nicht dargestellt werden");
    expect(await gallery.locator("code.language-html").textContent()).toContain("\t<script>window.__markdownExecution = true</script>");
    await expect(gallery.locator("code.language-html").locator("..")).toHaveCSS("white-space", "pre");
    expect(await learner.evaluate(() => (window as unknown as { __markdownExecution?: boolean }).__markdownExecution)).toBeUndefined();
    await teacher.goto(`/teaching/units/${seeded.unitId}/print`);
    await teacher.getByRole("checkbox", { name: "Grundrechte und digitale Kommunikation", exact: false }).check();
    await teacher.getByRole("checkbox", { name: /Mermaid-Typen/ }).check();
    const downloadPromise = teacher.waitForEvent("download");
    await teacher.getByRole("button", { name: "PDF herunterladen" }).click();
    const download = await downloadPromise;
    const pdfPath = info.outputPath("mermaid-print.pdf");
    await download.saveAs(pdfPath);
    const inspected = JSON.parse(execFileSync(resolve("../.venv/bin/python"), ["-c", "import json,sys\nfrom pypdf import PdfReader\np=PdfReader(sys.argv[1]).pages\nprint(json.dumps({'images':sum(len(x.images) for x in p),'text':' '.join(x.extract_text() for x in p)}))", pdfPath]).toString());
    expect(inspected.images).toBeGreaterThanOrEqual(2);
    expect(inspected.text).toContain("Das Diagramm konnte nicht dargestellt werden");
    expect(inspected.text).not.toContain("Alice->>Bob: Hallo");
    expect(inspected.text).toContain("Grundrechte und digitale Kommunikation");
    const denied = await learner.request.post(`/api/teaching/units/${seeded.unitId}/printable-pdf`, { headers: apiHeaders(), data: { material_ids: [], task_ids: [] } });
    expect(denied.status()).toBe(403);
  } finally {
    await learnerContext.close();
    await teacherContext.close();
  }
});
