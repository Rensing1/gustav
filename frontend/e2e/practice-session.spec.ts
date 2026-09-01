import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { apiHeaders } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";
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
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

function minimalH5pPackage(): Buffer {
  const fixture = resolve(projectRoot, "backend/tests_e2e/fixtures/h5p/minimal");
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

test("@feature-acceptance teacher authors and learner completes deterministic native and H5P practice", async ({ browser }) => {
  test.setTimeout(180_000);
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
            name: "minimal.h5p",
            mimeType: "application/zip",
            buffer: minimalH5pPackage()
          }
        }
      }
    );
    expect(importResponse.ok(), await importResponse.text()).toBe(true);
    const imported = await importResponse.json() as { h5p?: { content_id?: string } };
    const contentId = String(imported.h5p?.content_id ?? "");
    expect(contentId).toMatch(/^[1-9][0-9]*$/);
    registerE2EH5PContent(contentId, teacherEmail);

    await learner.page.goto(
      `/learning/practice?course_id=${seeded.courseId}&practice_module_id=${seeded.practiceModuleId}`
    );
    await expect(learner.page.getByRole("heading", { name: "Üben" })).toBeVisible();
    await learner.page.getByRole("button", { name: /Aufgabe.*starten/ }).click();

    let sawNative = false;
    let sawH5p = false;
    for (let step = 0; step < 6; step += 1) {
      const activeResponse = await learner.page.request.get(
        `${webBase}/api/learning/practice/sessions/active`
      );
      if (activeResponse.status() === 204) break;
      expect(activeResponse.ok(), await activeResponse.text()).toBe(true);
      const active = await activeResponse.json() as {
        current_item: { kind: "native" | "h5p"; task_id: string; presentation_number: number };
      };

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
        const player = learner.page.locator("h5p-player");
        await expect(player).toBeVisible({ timeout: 30_000 });
        await player.evaluate((element, id) => {
          element.dispatchEvent(new CustomEvent("xAPI", {
            detail: {
              statement: {
                id,
                verb: { id: "http://adlnet.gov/expapi/verbs/completed" },
                result: { completion: true, score: { raw: 2, max: 2 } }
              }
            }
          }));
        }, `practice-h5p-deterministic-${step}`);
      }

      await expect(
        learner.page.getByRole("heading", { name: /Sicher beantwortet|Teilweise beantwortet|Noch nicht sicher/ })
      ).toBeVisible({ timeout: 30_000 });
      await learner.page.getByRole("button", { name: "Nächste Aufgabe" }).click();
      if (await learner.page.getByRole("heading", { name: "Übung geschafft" }).isVisible()) break;
    }

    expect(sawNative).toBe(true);
    expect(sawH5p).toBe(true);
    await expect(learner.page.getByRole("heading", { name: "Übung geschafft" })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
