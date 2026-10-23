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
  for (const scenario of ["choice", "large"] as const) {
    test(`@feature-acceptance reloads an H5P task without losing state (${profile}, ${scenario})`, async ({ browser }) => {
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
        ].join("\n"), resolve(root, scenario === "large" ? "frontend/e2e/fixtures/h5p-large-state" : "frontend/e2e/fixtures/h5p-multichoice-design")]);
        const imported = await teacher.request.post(`${webBase}/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}/tasks/${seeded.taskId}/h5p/import`, {
          headers: { origin: webBase }, multipart: { file: { name: "reload.h5p", mimeType: "application/zip", buffer: pkg } }
        });
        expect(imported.ok(), await imported.text()).toBe(true);
        const contentId = String((await imported.json()).h5p.content_id);
        registerE2EH5PContent(contentId, teacherEmail);
        const isStateRead = (response: { url(): string; request(): { method(): string } }) =>
          response.url().includes(`/h5p/contentUserData/${contentId}/state/0`) && response.request().method() === "GET";
        const initialState = learner.waitForResponse(isStateRead);
        await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
        await learner.getByRole("button", { name: /beginnen/ }).first().click();
        await expect(learner.locator(scenario === "large" ? ".h5p-state-regression" : ".h5p-multichoice")).toBeVisible();
        const stateUrl = (await initialState).url();
        const longAnswer = "Äußere Begründung zur Aufgabe. ".repeat(4000);
        if (scenario === "large") {
          await learner.getByRole("textbox", { name: "Ausführliche Antwort" }).fill(longAnswer);
        } else {
        await learner.getByRole("radio", { name: /Vier/ }).press("Space");
        await learner.getByRole("button", { name: /Check|Die Antworten überprüfen/ }).click();
        await expect(learner.getByText("Gespeichert (1/1).")).toBeVisible();
        }
        const submissionsUrl = `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions`;
        const before = await learner.request.get(submissionsUrl);
        expect(before.ok()).toBe(true);
        const submissions = await before.json();
        if (scenario === "choice") expect(submissions).toEqual(expect.arrayContaining([expect.objectContaining({ kind: "h5p", score_raw: 1, score_max: 1 })]));
        else expect(submissions).toEqual([]);

        const readCurrentState = () => learner.evaluate(() => {
          const h5p = (window as typeof window & { H5P: { instances: Array<{ getCurrentState(): unknown }> } }).H5P;
          return h5p.instances[0].getCurrentState();
        });
        for (let reload = 0; reload < 2; reload += 1) {
          let currentState = await readCurrentState();
          if (scenario === "large") {
            const answer = `${longAnswer} Letzte Änderung ${reload}.`;
            currentState = { answer };
            // Change and reload in one browser task: no foreground timer can save this.
            const navigation = learner.waitForEvent("load");
            await learner.evaluate((value) => {
              const textarea = document.querySelector(".h5p-state-regression textarea") as HTMLTextAreaElement;
              textarea.value = value; textarea.dispatchEvent(new Event("input", { bubbles: true }));
              location.reload();
            }, answer);
            await navigation;
          } else await learner.reload();
          await expect(learner.locator(scenario === "large" ? ".h5p-state-regression" : ".h5p-multichoice")).toBeVisible();
          await expect.poll(readCurrentState).toEqual(currentState);
          // Navigation need not expose a response from the old document.
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
        if (scenario === "choice") {
        const retry = learner.getByRole("button", { name: /Retry|Die Aufgabe wiederholen/ });
        if (await retry.isVisible()) await retry.click();
        await learner.getByRole("radio", { name: /Vier/ }).press("Space");
        await expect(learner.getByRole("radio", { name: /Vier/ })).toHaveAttribute("aria-checked", "true");
        } else {
          const answer = learner.getByRole("textbox", { name: "Ausführliche Antwort" });
          await expect(answer).toHaveValue(`${longAnswer} Letzte Änderung 1.`);
          await answer.fill(`${longAnswer} Im Vordergrund bestätigt.`);
          await expect(learner.getByText("Bearbeitungsstand gespeichert.", { exact: true })).toBeVisible();
          const stored = await learner.request.get(stateUrl);
          expect(JSON.parse((await stored.json()).data)).toEqual({ answer: `${longAnswer} Im Vordergrund bestätigt.` });
          await learner.locator(".learner-task-header button").click();
          await learner.getByRole("button", { name: /beginnen/ }).first().click();
          await expect(learner.getByRole("textbox", { name: "Ausführliche Antwort" })).toHaveValue(`${longAnswer} Im Vordergrund bestätigt.`);
          await learner.getByRole("textbox", { name: "Ausführliche Antwort" }).fill(`${longAnswer} Nach Rückkehr überarbeitet.`);
          await expect(learner.getByText("Bearbeitungsstand gespeichert.", { exact: true })).toBeVisible();
          const reopened = await learner.request.get(stateUrl);
          expect(JSON.parse((await reopened.json()).data)).toEqual({ answer: `${longAnswer} Nach Rückkehr überarbeitet.` });
        }
        expect(errors).toEqual([]);
      } finally {
        await learnerContext.close();
        await teacherContext.close();
      }
    });
  }
}
