import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { expect, test, type Page, type TestInfo } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedH5pVisualSmokeUnit } from "./support/seed-data";
import { expectDesignContrast } from "./support/design-contrast";

test.use({ actionTimeout: 15_000 });

async function pictures(page: Page, info: TestInfo, name: string) {
  for (const theme of ["light", "dark"]) {
    const desiredToggle = theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren";
    const toggle = page.getByRole("button", { name: desiredToggle, exact: true });
    if (await toggle.count()) await toggle.click();
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      if (name === "editor") {
        const frame = page.frameLocator(".h5p-editor-iframe");
        await expect.poll(() => frame.locator("html").evaluate((root) => ({
          width: root.clientWidth,
          scrollWidth: root.scrollWidth,
          elements: Array.from(root.querySelectorAll("*"))
            .filter((element) => !element.closest("table") && (element.getBoundingClientRect().right > root.clientWidth + 1 || element.scrollWidth > element.clientWidth + 1))
            .map((element) => ({ tag: element.tagName, className: element.className, width: element.getBoundingClientRect().width, scroll: element.scrollWidth })).slice(-25),
        })).then((result) => result.scrollWidth <= result.width + 1 ? null : JSON.stringify(result))).toBeNull();
        await expectDesignContrast(frame.locator(".h5peditor-label, .h5peditor-field-description, .h5peditor label, .h5peditor-button-textual, .list-item-title-bar, .h5peditor input:not([type=checkbox]):not([type=radio])"));
        await expect(frame.locator(".h5p-tutorial-url-label")).toBeVisible();
        await expectDesignContrast(frame.locator(".h5p-tutorial-url-label, .h5p-example-url-label, .h5peditor-copy-button, .h5peditor-paste-button"));
        expect(await frame.locator(".group > .title, .common > .h5peditor-label").evaluateAll((titles) => titles.filter((title) => title.getClientRects().length).every((title) => {
          const range = document.createRange();
          range.selectNodeContents(title);
          const text = range.getBoundingClientRect(), box = title.getBoundingClientRect();
          return text.bottom <= box.bottom + 1;
        }))).toBe(true);
        for (const field of await frame.locator('.h5peditor input:not([type=checkbox]):not([type=radio]), .h5peditor-button-textual, .h5p-tutorial-url, .h5p-example-url, .h5peditor-copy-button, .h5peditor-paste-button').all()) {
          if (await field.isVisible()) expect((await field.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        }
      } else {
        for (const action of await page.locator(".h5p-joubelui-button, .h5p-alternative-container").all()) {
          if (!await action.isVisible()) continue;
          const box = (await action.boundingBox())!;
          expect(box.height).toBeGreaterThanOrEqual(44);
          expect(box.width).toBeGreaterThanOrEqual(44);
        }
        for (const surface of await page.locator(".h5p-feedback-inner, .h5p-joubelui-score-bar").all()) {
          if (await surface.isVisible()) await expect(surface).toHaveCSS("background-color", theme === "dark" ? "rgb(26, 26, 26)" : "rgb(255, 255, 255)");
        }
        await expectDesignContrast(page.locator(".h5p-alternative-container, .h5p-joubelui-button, .h5p-question-feedback, .feedback-text, .h5p-feedback-inner, .h5p-feedback-inner p, .h5p-feedback-text"));
      }
      await page.screenshot({ path: info.outputPath(`${name}-${width}-${theme}.png`), fullPage: true });
    }
  }
}

test("@feature-acceptance German H5P editor preserves author text and multiple choice states remain usable", async ({ browser }, info) => {
  test.setTimeout(180_000);
  const teacherEmail = e2eEmail("teacher"), learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const tc = await newBrowserContext(browser, { locale: "de-DE" }), lc = await newBrowserContext(browser, { locale: "de-DE" });
  const teacher = await tc.newPage(), learner = await lc.newPage();
  try {
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedH5pVisualSmokeUnit(teacher, learner, `H5P Design ${Date.now()}`);
    const base = `/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}/tasks/${seeded.taskId}/h5p`;
    const root = resolve(process.cwd(), "..");
    const pkg = execFileSync(resolve(root, ".venv/bin/python"), ["-c", "import io,pathlib,sys,zipfile\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:\n for p in pathlib.Path(sys.argv[1]).rglob('*'):\n  if p.is_file(): z.write(p,p.relative_to(sys.argv[1]))\nsys.stdout.buffer.write(b.getvalue())", resolve(root, "frontend/e2e/fixtures/h5p-multichoice-design")]);
    const imported = await teacher.request.post(`${webBase}${base}/import`, { headers: { origin: webBase }, multipart: { file: { name: "design.h5p", mimeType: "application/zip", buffer: pkg } } });
    expect(imported.ok(), await imported.text()).toBe(true);
    const contentId = String((await imported.json()).h5p.content_id);
    registerE2EH5PContent(contentId, teacherEmail);
    await teacher.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.sectionId}`);
    await teacher.getByRole("button", { name: /H5P-Aufgabe/ }).click();
    await expect(teacher.locator('[data-role="h5p-status"]')).toHaveText(/Editor geladen/, { timeout: 30_000 });
    const editor = teacher.frameLocator(".h5p-editor-iframe");
    await expect(editor.getByText("Frage", { exact: true })).toBeVisible();
    await expect(editor.getByText("Titel", { exact: true })).toBeVisible();
    await expect(editor.getByText(/Keep this author text/)).toBeVisible();
    await pictures(teacher, info, "editor");
    for (const theme of ["light", "dark"]) {
      const toggle = teacher.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
      if (await toggle.count()) await toggle.click();
      await editor.locator(".h5p-li .remove").first().click();
      const cancel = editor.locator("button.h5p-core-cancel-button");
      await expect(cancel).toBeVisible();
      await expect(editor.locator(".h5p-confirmation-dialog-background")).toHaveCSS("position", "absolute");
      await expectDesignContrast(editor.locator(".h5p-confirmation-dialog-header, .h5p-confirmation-dialog-text"));
      expect(await editor.locator(".h5p-confirmation-dialog-popup").evaluate((dialog) => {
        const box = dialog.getBoundingClientRect();
        return box.left >= 0 && box.right <= document.documentElement.clientWidth + 1;
      })).toBe(true);
      await expectDesignContrast(editor.locator("button.h5p-core-button, button.h5p-core-cancel-button"));
      for (const button of await editor.locator("button.h5p-core-button, button.h5p-core-cancel-button").all()) {
        if (!await button.isVisible()) continue;
        expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
        await button.hover();
        await button.focus();
        await teacher.keyboard.press("Tab");
        await teacher.keyboard.press("Shift+Tab");
        await expect(button).toBeFocused();
        await expect(button).not.toHaveCSS("outline-style", "none");
        await expectDesignContrast(button);
      }
      await editor.locator(".h5p-confirmation-dialog-popup").screenshot({ path: info.outputPath(`editor-confirmation-${theme}.png`) });
      await cancel.click();
      await expect(editor.locator(".h5p-li")).toHaveCount(2);
    }
    await teacher.getByRole("button", { name: "H5P speichern", exact: true }).click();
    await expect(teacher.getByText("H5P-Inhalt gespeichert.").filter({ visible: true })).toBeVisible();
    await teacher.reload();
    if (!await teacher.locator('[data-role="h5p-status"]').count()) await teacher.getByRole("button", { name: /H5P-Aufgabe/ }).click();
    await expect(editor.getByText(/Keep this author text/)).toBeVisible({ timeout: 30_000 });

    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.getByRole("button", { name: /beginnen/ }).first().click();
    await expect(learner.locator(".h5p-multichoice")).toBeVisible({ timeout: 30_000 });
    await expect(learner.getByText(/Keep this author text/)).toBeVisible();
    await expect(learner.getByRole("button", { name: "Lesbare Ansicht", exact: true })).toHaveCount(0);
    await pictures(learner, info, "choice-ready");
    await learner.getByRole("radio", { name: /Drei/ }).press("Space");
    await learner.getByRole("button", { name: /Die Antworten überprüfen/ }).click();
    await expect(learner.getByText("Gespeichert (0/1).")).toBeVisible();
    await pictures(learner, info, "choice-wrong");
    await learner.getByRole("button", { name: /Die Aufgabe wiederholen/ }).click();
    await learner.getByRole("radio", { name: /Vier/ }).press("Space");
    await learner.getByRole("button", { name: /Die Antworten überprüfen/ }).click();
    await expect(learner.getByText("Gespeichert (1/1).")).toBeVisible();
    await expect(learner.locator(".h5p-joubelui-score-numeric")).toHaveText(/1\s*\/\s*1/);
    await pictures(learner, info, "choice-correct");
    await learner.reload();
    await expect(learner.locator(".h5p-multichoice")).toBeVisible({ timeout: 30_000 });
  } finally {
    await lc.close().catch(() => {});
    await tc.close().catch(() => {});
  }
});
