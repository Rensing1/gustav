import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { devices } from "@playwright/test";
import { expect, test } from "./support/feature-test";
import { newBrowserContext } from "./support/browser-context";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { installBrowserCompatibilityProfile } from "./support/ios-15-3-profile";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedH5pVisualSmokeUnit } from "./support/seed-data";

for (const profile of ["combined", "modern"] as const) {
  test(`@feature-acceptance reloads a scored H5P task without runtime errors (${profile})`, async ({ browser }) => {
    test.setTimeout(120_000);
    const teacherEmail = e2eEmail("teacher"), learnerEmail = e2eEmail("learner");
    await ensureTeacherUser(teacherEmail, e2ePassword);
    await ensureLearnerUser(learnerEmail, e2ePassword);
    const teacherContext = await newBrowserContext(browser, { baseURL: webBase, locale: "de-DE" });
    const learnerContext = await newBrowserContext(browser, { ...devices["iPad Pro 11 landscape"], baseURL: webBase, locale: "de-DE" });
    await installBrowserCompatibilityProfile(learnerContext, profile);
    const teacher = await teacherContext.newPage(), learner = await learnerContext.newPage();
    const errors: string[] = [];
    learner.on("pageerror", (error) => errors.push(error.message));
    try {
      await login(teacher, teacherEmail, e2ePassword);
      await login(learner, learnerEmail, e2ePassword);
      const seeded = await seedH5pVisualSmokeUnit(teacher, learner, `H5P Neuladen ${Date.now()}`);
      const root = resolve(process.cwd(), "..");
      const pkg = execFileSync(resolve(root, ".venv/bin/python"), ["-c", [
        "import io, pathlib, sys, zipfile", "buffer = io.BytesIO()",
        "with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:",
        "    for path in pathlib.Path(sys.argv[1]).rglob('*'):",
        "        if path.is_file(): archive.write(path, path.relative_to(sys.argv[1]))",
        "sys.stdout.buffer.write(buffer.getvalue())"
      ].join("\n"), resolve(root, "frontend/e2e/fixtures/h5p-multichoice-design")]);
      const imported = await teacher.request.post(`${webBase}/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}/tasks/${seeded.taskId}/h5p/import`, {
        headers: { origin: webBase }, multipart: { file: { name: "reload.h5p", mimeType: "application/zip", buffer: pkg } }
      });
      expect(imported.ok()).toBe(true);
      const contentId = String((await imported.json()).h5p.content_id);
      registerE2EH5PContent(contentId, teacherEmail);
      const isStateRead = (response: { url(): string; request(): { method(): string } }) =>
        response.url().includes(`/h5p/contentUserData/${contentId}/state/0`) && response.request().method() === "GET";
      const initialState = learner.waitForResponse(isStateRead);
      await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await learner.getByRole("button", { name: /beginnen/ }).first().click();
      await expect(learner.locator(".h5p-multichoice")).toBeVisible();
      const stateUrl = (await initialState).url();
      await learner.getByRole("radio", { name: /Vier/ }).press("Space");
      await learner.getByRole("button", { name: /Check|Die Antworten überprüfen/ }).click();
      await expect(learner.getByText("Gespeichert (1/1).")).toBeVisible();
      const submissionsUrl = `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions`;
      const before = await learner.request.get(submissionsUrl);
      expect(before.ok()).toBe(true);
      const submissions = await before.json();
      expect(submissions).toEqual(expect.arrayContaining([expect.objectContaining({ kind: "h5p", score_raw: 1, score_max: 1 })]));

      const readCurrentState = () => learner.evaluate(() => {
        const h5p = (window as typeof window & { H5P: { instances: Array<{ getCurrentState(): unknown }> } }).H5P;
        return h5p.instances[0].getCurrentState();
      });
      for (let reload = 0; reload < 2; reload += 1) {
        const currentState = await readCurrentState();
        await learner.reload();
        await expect(learner.locator(".h5p-multichoice")).toBeVisible();
        await expect.poll(readCurrentState).toEqual(currentState);
        // WebKit need not expose the old document's Beacon response after navigation.
        // Read both the real server state and the restored player instead.
        const state = await learner.request.get(stateUrl);
        expect(errors).toEqual([]);
        expect(state.status()).toBe(200);
        const payload = await state.json();
        expect(payload.success).toBe(true);
        expect(JSON.parse(payload.data)).toEqual(currentState);
        expect(state.headers()["cache-control"]).toBe("private, no-store");
      }
      const after = await learner.request.get(submissionsUrl);
      expect(after.ok()).toBe(true);
      expect(await after.json()).toEqual(submissions);
      const retry = learner.getByRole("button", { name: /Retry|Die Aufgabe wiederholen/ });
      if (await retry.isVisible()) await retry.click();
      await learner.getByRole("radio", { name: /Vier/ }).press("Space");
      await expect(learner.getByRole("radio", { name: /Vier/ })).toHaveAttribute("aria-checked", "true");
      expect(errors).toEqual([]);
    } finally {
      await learnerContext.close();
      await teacherContext.close();
    }
  });
}
