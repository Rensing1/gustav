import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { expect, test, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerPracticeCourse } from "./support/seed-data";

test.use({ actionTimeout: 15_000 });

const root = resolve(process.cwd(), "..");

async function checkLayout(page: Page) {
  const board = page.locator(".h5p-dragquestion > .h5p-question-content > .h5p-inner");
  await expect(board).toBeVisible();
  await expect(page.getByRole("button", { name: "Lesbare Ansicht", exact: true })).toHaveAttribute("aria-pressed", "true");
  const boxes = await page.locator(".h5p-dragquestion .h5p-draggable").evaluateAll((elements) =>
    elements.map((element) => {
      const b = element.getBoundingClientRect();
      return { x: b.x, y: b.y, right: b.right, bottom: b.bottom };
    })
  );
  await expect.poll(() => page.locator(".h5p-dragquestion .h5p-draggable").evaluateAll((elements) => elements.every((element) => {
    const box = element.getBoundingClientRect();
    return parseFloat(getComputedStyle(element).fontSize) >= 16 && [...element.querySelectorAll("p")].every((p) => {
      const text = p.getBoundingClientRect();
      return parseFloat(getComputedStyle(p).fontSize) >= 16 && text.top >= box.top - 1 && text.bottom <= box.bottom + 1 && p.scrollWidth <= p.clientWidth + 1;
    });
  }))).toBe(true);
  const area = await board.boundingBox();
  for (let i = 0; i < boxes.length; i += 1) {
    expect(boxes[i].right).toBeLessThanOrEqual(area!.x + area!.width + 1);
    for (let j = i + 1; j < boxes.length; j += 1) {
      const a = boxes[i], b = boxes[j];
      expect(a.right <= b.x || b.right <= a.x || a.bottom <= b.y || b.bottom <= a.y).toBe(true);
    }
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
}

async function checkContrast(page: Page) {
  // Check the actual foreground/background pair after all theme/library CSS.
  const ratios = await page.locator(".h5p-dragquestion .h5p-draggable, .h5p-dragquestion .h5p-label, .h5p-dragquestion .h5p-joubelui-button").evaluateAll((elements) => {
    function rgb(value: string): number[] {
      const values = value.match(/[\d.]+/g)!.map(Number);
      return values.slice(0, 3);
    }
    function luminance(values: number[]) {
      const [r, g, b] = values.map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }
    return elements.map((element) => {
      const s = getComputedStyle(element);
      let bg = s.backgroundColor;
      let parent = element.parentElement;
      while (bg === "rgba(0, 0, 0, 0)" && parent) { bg = getComputedStyle(parent).backgroundColor; parent = parent.parentElement; }
      const a = luminance(rgb(s.color)), b = luminance(rgb(bg));
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    });
  });
  expect(ratios.length).toBeGreaterThanOrEqual(13);
  ratios.forEach((ratio) => expect(ratio).toBeGreaterThanOrEqual(4.5));
}

test("@feature-acceptance H5P drag cards remain readable and usable across themes and widths", async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const teacherEmail = e2eEmail("teacher"), learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const tc = await newBrowserContext(browser), lc = await newBrowserContext(browser, { viewport: { width: 1280, height: 900 } });
  const teacher = await tc.newPage(), learner = await lc.newPage();
  try {
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedLearnerPracticeCourse(teacher, learner, `H5P Layout ${Date.now()}`, false);
    await teacher.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.practiceModuleId}`);
    await teacher.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    const form = teacher.getByTestId("teacher-node-editor-create-slot");
    await form.getByLabel("Aufgabentyp").selectOption("h5p");
    await form.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    await expect(teacher.getByText("Aufgabe angelegt.")).toBeVisible();
    await expect(teacher.locator('[data-role="h5p-status"]')).toHaveText(/Bereit\.|Editor geladen/, { timeout: 30_000 });
    const source = resolve(root, "frontend/e2e/fixtures/h5p-drag-layout");
    const pkg = process.env.H5P_LAYOUT_PACKAGE ? readFileSync(process.env.H5P_LAYOUT_PACKAGE) : execFileSync(resolve(root, ".venv/bin/python"), ["-c", "import io,pathlib,sys,zipfile\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:\n for p in pathlib.Path(sys.argv[1]).rglob('*'):\n  if p.is_file(): z.write(p,p.relative_to(sys.argv[1]))\nsys.stdout.buffer.write(b.getvalue())", source]);
    const content = JSON.parse(execFileSync(resolve(root, ".venv/bin/python"), ["-c", "import io,json,sys,zipfile; print(zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())).read('content/content.json').decode())"], { input: pkg }).toString());
    const zones = content.question.task.dropZones as Array<{ correctElements: string[]; label: string }>;
    const correctZone = (index: number) => zones.findIndex((zone) => zone.correctElements.includes(String(index)));
    const target = (index: number) => learner.getByRole("button", { name: new RegExp(`^Ablagefeld ${index + 1} von 6\\.`) });
    const label = (index: number) => zones[index].label.replace(/<[^>]+>/g, "");
    const chooserPromise = teacher.waitForEvent("filechooser");
    await teacher.getByRole("button", { name: /^Importieren$/i }).click();
    const chooser = await chooserPromise;
    await chooser.setFiles({ name: "drag-layout.h5p", mimeType: "application/zip", buffer: pkg });
    await expect(teacher.getByText("Editor geladen (H5P.DragQuestion 1.14).").filter({ visible: true })).toBeVisible({ timeout: 30_000 });
    await teacher.getByRole("button", { name: /^H5P speichern$/i }).click();
    await expect(teacher.getByText("H5P-Inhalt gespeichert.").filter({ visible: true })).toBeVisible();
    const tasks = await (await teacher.request.get(`${webBase}/api/teaching/units/${seeded.unitId}/modules/${seeded.practiceModuleId}/tasks`)).json();
    registerE2EH5PContent(String(tasks[0].h5p.content_id), teacherEmail);

    await learner.goto("/learning/practice");
    await learner.getByRole("checkbox", { name: /Wiederholen/ }).locator("..").click();
    await learner.getByRole("button", { name: /Aufgabe.*starten/ }).click();
    await expect(learner.locator(".h5p-dragquestion .h5p-draggable")).toHaveCount(6, { timeout: 30_000 });
    for (const theme of ["light", "dark"] as const) {
      if (theme === "dark") await learner.getByRole("button", { name: "Dark Mode aktivieren" }).click();
      for (const width of [1440, 1024, 390, 320]) {
        await learner.setViewportSize({ width, height: 900 });
        await checkLayout(learner);
        await checkContrast(learner);
        await learner.screenshot({ path: testInfo.outputPath(`drag-readable-${width}-${theme}.png`), fullPage: true });
        const stage = learner.locator(".h5p-task-viewport > div");
        const before = (await stage.boundingBox())!.width;
        await learner.getByRole("button", { name: "Vergrößern", exact: true }).click();
        await expect.poll(async () => (await stage.boundingBox())!.width).toBeGreaterThan(before);
        await learner.getByRole("button", { name: "Verkleinern", exact: true }).click();
        await expect.poll(async () => (await stage.boundingBox())!.width).toBeLessThanOrEqual(before + 2);
        await learner.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
        await expect.poll(() => learner.locator(".h5p-task-viewport").evaluate((region) => region.scrollWidth <= region.clientWidth + 1)).toBe(true);
        if (width === 390) await learner.screenshot({ path: testInfo.outputPath(`drag-overview-${width}-${theme}.png`), fullPage: true });
        await learner.getByRole("button", { name: "Lesbare Ansicht", exact: true }).click();
      }
    }
    const lastCard = learner.getByRole("button", { name: /Ziehbares Element 6 von 6/ });
    await lastCard.focus();
    await expect.poll(async () => {
      const item = await lastCard.boundingBox(), region = await learner.locator(".h5p-task-viewport").boundingBox();
      return item!.y >= region!.y - 1 && item!.y + item!.height <= region!.y + region!.height + 1;
    }).toBe(true);
    await learner.setViewportSize({ width: 1280, height: 900 });
    await checkLayout(learner);

    const card = learner.getByRole("button", { name: /Ziehbares Element 1 von 6/ });
    const firstTarget = correctZone(0), wrongTarget = (firstTarget + 1) % 6;
    await card.dragTo(target(wrongTarget));
    await expect(card).toContainText(`In Ablagefeld ${label(wrongTarget)} abgelegt`);
    await card.dragTo(target(firstTarget));
    await expect(card).toContainText(`In Ablagefeld ${label(firstTarget)} abgelegt`);
    await checkContrast(learner);
    for (let i = 2; i <= 6; i += 1) {
      // Keyboard selection also exercises the click/select alternative to dragging.
      await learner.getByRole("button", { name: new RegExp(`Ziehbares Element ${i} von 6`) }).press("Enter");
      await target(correctZone(i - 1)).press("Enter");
    }
    await learner.screenshot({ path: testInfo.outputPath("desktop-dark-complete.png"), fullPage: true });
    await learner.getByRole("button", { name: /Antworten auswerten/ }).click();
    await expect(learner.getByRole("heading", { name: "Sicher beantwortet", exact: true })).toBeVisible({ timeout: 30_000 });
    await learner.reload();
    await expect(learner.getByRole("heading", { name: "Sicher beantwortet", exact: true })).toBeVisible();
  } finally {
    await lc.close().catch(() => {});
    await tc.close().catch(() => {});
  }
});
