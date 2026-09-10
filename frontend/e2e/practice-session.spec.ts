import { newBrowserContext } from "./support/browser-context";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { apiHeaders } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Browser, type BrowserContext, type Page, type TestInfo } from "./support/feature-test";
import { expectDesignContrast } from "./support/design-contrast";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { seedLearnerPracticeCourse } from "./support/seed-data";
import {
  completeQueuedFeedbackDeterministically,
  holdProviderWorker,
  releaseProviderWorker
} from "./support/submission-finalization-fixture";


const projectRoot = resolve(process.cwd(), "..");
const python = resolve(projectRoot, ".venv/bin/python");

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await newBrowserContext(browser, { baseURL: webBase, locale: "de-DE" });
  context.setDefaultTimeout(15_000);
  return { context, page: await context.newPage() };
}

function practiceH5pPackage(): Buffer {
  const fixture = resolve(projectRoot, "frontend/e2e/fixtures/h5p-multichoice-design");
  const program = [
    "import io, pathlib, sys, zipfile",
    "source = pathlib.Path(sys.argv[1])",
    "buffer = io.BytesIO()",
    "with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:",
    "    for path in sorted(source.rglob('*')):",
    "        if path.is_file(): archive.write(path, path.relative_to(source).as_posix())",
    "sys.stdout.buffer.write(buffer.getvalue())"
  ].join("\n");
  return execFileSync(python, ["-c", program, fixture], { cwd: projectRoot });
}

async function pictures(page: Page, info: TestInfo, state: string) {
  for (const theme of ["light", "dark"]) {
    const toggle = page.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
    if (await toggle.count()) await toggle.click();
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      await expect(async () => expectDesignContrast(page.locator(".practice-eyebrow, .practice-session__topline p, .practice-session h2, .practice-feedback h3, .workspace-link-action"))).toPass({ timeout: 2000 });
      await page.screenshot({ path: info.outputPath(`${state}-${width}-${theme}.png`), fullPage: true, animations: "disabled" });
    }
  }
}

test("@feature-acceptance teacher authors and learner completes native repetition and real H5P practice", async ({ browser }, info) => {
  test.setTimeout(240_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);

  try {
    await login(teacher.page, teacherEmail, e2ePassword);
    await login(learner.page, learnerEmail, e2ePassword);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerPracticeCourse(
      teacher.page,
      learner.page,
      `Practice ${unique}`
    );

    await teacher.page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.practiceModuleId}`);
    await teacher.page.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    const createForm = teacher.page.getByTestId("teacher-node-editor-create-slot");
    await createForm.getByLabel("Aufgabentyp").selectOption("h5p");
    await createForm.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    await expect(teacher.page.getByText("Aufgabe angelegt.")).toBeVisible();

    await expect.poll(async () => {
      const response = await teacher.page.request.get(
        `${webBase}/api/teaching/units/${seeded.unitId}/modules/${seeded.practiceModuleId}/tasks`
      );
      if (!response.ok()) return false;
      const tasks = await response.json() as Array<{ kind: string }>;
      return tasks.some((task) => task.kind === "h5p");
    }).toBe(true);

    const tasksResponse = await teacher.page.request.get(
      `${webBase}/api/teaching/units/${seeded.unitId}/modules/${seeded.practiceModuleId}/tasks`
    );
    expect(tasksResponse.ok(), await tasksResponse.text()).toBe(true);
    const tasks = await tasksResponse.json() as Array<{ id: string; kind: string }>;
    const h5pTask = tasks.find((task) => task.kind === "h5p");
    expect(h5pTask?.id).toBeTruthy();

    const headers = apiHeaders(`/teaching/units/${seeded.unitId}`);
    delete (headers as Partial<typeof headers>)["content-type"];
    const importResponse = await teacher.page.request.post(
      `${webBase}/api/teaching/units/${seeded.unitId}/modules/${seeded.practiceModuleId}/tasks/${h5pTask!.id}/h5p/import`,
      {
        headers,
        multipart: {
          file: {
            name: "multiple-choice.h5p",
            mimeType: "application/zip",
            buffer: practiceH5pPackage()
          }
        }
      }
    );
    expect(importResponse.ok(), await importResponse.text()).toBe(true);
    const imported = await importResponse.json() as { h5p?: { content_id?: string } };
    const contentId = String(imported.h5p?.content_id ?? "");
    expect(contentId).toMatch(/^[1-9][0-9]*$/);
    registerE2EH5PContent(contentId, teacherEmail);
    await teacher.page.reload();
    await teacher.page.getByRole("button", { name: /H5P-Aufgabe/ }).click();
    await expect(teacher.page.locator('[data-role="h5p-status"]')).toHaveText(/Editor geladen/, { timeout: 30_000 });
    await teacher.page.getByRole("button", { name: "H5P speichern", exact: true }).click();
    await expect(teacher.page.getByText("H5P-Inhalt gespeichert.").filter({ visible: true })).toBeVisible();

    const accessPath = `${webBase}/api/learning/courses/${seeded.courseId}/h5p/contents/${contentId}/access`;
    const playerPath = `${webBase}/h5p/player/model?course_id=${seeded.courseId}&content_id=${contentId}`;
    expect((await learner.page.request.get(accessPath)).status()).toBe(204);
    expect((await learner.page.request.get(playerPath)).status()).toBe(200);

    await learner.page.goto(
      `/learning/practice?course_id=${seeded.courseId}&practice_module_id=${seeded.practiceModuleId}`
    );
    await expect(learner.page.getByRole("heading", { name: "Üben" })).toBeVisible();
    await learner.page.getByRole("button", { name: /Aufgabe.*starten/ }).click();

    let sawNative = false;
    let sawH5p = false;
    let sawRepetition = false;
    let firstAttemptId = "";
    let firstAttempt: unknown;
    for (let step = 0; step < 6; step += 1) {
      const activeResponse = await learner.page.request.get(
        `${webBase}/api/learning/practice/sessions/active`
      );
      if (activeResponse.status() === 204) break;
      expect(activeResponse.ok(), await activeResponse.text()).toBe(true);
      const active = await activeResponse.json() as {
        current_item: { kind: "native" | "h5p"; task_id: string; presentation_number: number; latest_attempt_id: string };
      };

      if (active.current_item.presentation_number === 2) {
        sawRepetition = true;
        await expect(learner.page.getByText("Wiederholung", { exact: true })).toBeVisible();
        await expect(learner.page.getByText("Du übst diese Aufgabe erneut. Deine bisherigen Antworten bleiben erhalten.")).toBeVisible();
        await pictures(learner.page, info, "repetition");
      } else {
        await expect(learner.page.getByText("Wiederholung", { exact: true })).toHaveCount(0);
        if (active.current_item.kind === "native") await pictures(learner.page, info, "first-presentation");
      }

      if (active.current_item.kind === "native") {
        sawNative = true;
        await holdProviderWorker();
        try {
          await learner.page.getByLabel("Deine Antwort").fill(
            "Ein roter Test zeigt, dass die neue Funktion vor der Implementierung wirklich fehlt."
          );
          await learner.page.getByRole("button", { name: "Antwort prüfen" }).click();
          await completeQueuedFeedbackDeterministically({
            courseId: seeded.courseId,
            taskId: active.current_item.task_id,
            learnerSub
          });
        } finally {
          await releaseProviderWorker();
        }
        await learner.page.reload();
      } else {
        sawH5p = true;
        await expect(learner.page.locator(".h5p-multichoice")).toBeVisible({ timeout: 30_000 });
        await learner.page.getByRole("radio", { name: /Vier/ }).press("Space");
        await learner.page.getByRole("button", { name: /Die Antworten überprüfen/ }).click();
      }

      await expect(
        learner.page.getByRole("heading", { name: /Sicher beantwortet|Teilweise beantwortet|Noch nicht sicher/ })
      ).toBeVisible({ timeout: 30_000 });
      if (active.current_item.kind === "native" && active.current_item.presentation_number === 1) {
        await learner.page.getByRole("button", { name: "Musterlösung ansehen" }).click();
        await expect(learner.page.getByRole("heading", { name: "Musterlösung", exact: true })).toBeVisible();
        await pictures(learner.page, info, "model-solution");
        const current = await (await learner.page.request.get(`${webBase}/api/learning/practice/sessions/active`)).json();
        firstAttemptId = current.current_item.latest_attempt_id;
        const response = await learner.page.request.get(`${webBase}/api/learning/practice/attempts/${firstAttemptId}`);
        expect(response.status()).toBe(200);
        firstAttempt = await response.json();
      }
      await learner.page.getByRole("button", { name: "Nächste Aufgabe" }).click();
      if (await learner.page.getByRole("heading", { name: "Übung geschafft" }).isVisible()) break;
    }

    expect(sawNative).toBe(true);
    expect(sawH5p).toBe(true);
    expect(sawRepetition).toBe(true);
    await expect(learner.page.getByRole("heading", { name: "Übung geschafft" })).toBeVisible();
    await pictures(learner.page, info, "completed");
    const retained = await learner.page.request.get(`${webBase}/api/learning/practice/attempts/${firstAttemptId}`);
    expect(retained.status()).toBe(200);
    expect(await retained.json()).toEqual(firstAttempt);

    const removed = await teacher.page.request.delete(
      `${webBase}/api/teaching/courses/${seeded.courseId}/members/${learnerSub}`,
      { headers: apiHeaders() }
    );
    expect(removed.status()).toBe(204);
    const denied = await learner.page.request.get(accessPath);
    expect(denied.status()).toBe(404);
    expect(denied.headers()["cache-control"]).toBe("private, no-store");
    // The sidecar retains its existing short-lived authorization cache (30s default).
    await expect.poll(async () => (await learner.page.request.get(playerPath)).status(), {
      timeout: 45_000,
      intervals: [1000]
    }).toBe(404);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
