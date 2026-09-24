import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { apiHeaders, expectApiOk } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { registerE2EH5PContent } from "./support/e2e-run-state";
import { expect, test, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerPracticeCourse } from "./support/seed-data";

const projectRoot = resolve(process.cwd(), "..");

function h5pPackage(): Buffer {
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
  return execFileSync(resolve(projectRoot, ".venv/bin/python"), ["-c", program, fixture]);
}

async function create(page: Page, path: string, data: Record<string, unknown>) {
  const response = await page.request.post(`${webBase}${path}`, { headers: apiHeaders(), data });
  await expectApiOk(response, 201);
  return response.json();
}

async function importH5P(
  teacher: Page,
  teacherEmail: string,
  unitId: string,
  moduleId: string,
  taskId: string
): Promise<string> {
  const headers = apiHeaders(`/teaching/units/${unitId}`);
  delete (headers as Partial<typeof headers>)["content-type"];
  const response = await teacher.request.post(
    `${webBase}/api/teaching/units/${unitId}/modules/${moduleId}/tasks/${taskId}/h5p/import`,
    {
      headers,
      multipart: {
        file: { name: "feedback-progress.h5p", mimeType: "application/zip", buffer: h5pPackage() }
      }
    }
  );
  await expectApiOk(response);
  const contentId = String((await response.json()).h5p?.content_id ?? "");
  expect(contentId).toMatch(/^[1-9][0-9]*$/);
  registerE2EH5PContent(contentId, teacherEmail);
  return contentId;
}

async function createH5PTask(
  teacher: Page,
  unitId: string,
  moduleId: string,
  instruction: string
): Promise<{ taskId: string; contentId: string }> {
  const target = await teacher.request.get(
    `${webBase}/api/teaching/units/${unitId}/modules/${moduleId}/content-target`
  );
  await expectApiOk(target);
  const sectionId = String((await target.json()).section_id);
  const task = await create(
    teacher,
    `/api/teaching/units/${unitId}/sections/${sectionId}/tasks`,
    { instruction_md: instruction, criteria: [], h5p: { content_id: null, display_options: {} } }
  );
  return { taskId: String(task.id), contentId: "" };
}

test("@feature-acceptance H5P feedback remains readable and full score unlocks the next module", async ({ browser }) => {
  test.setTimeout(240_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser, { baseURL: webBase, locale: "de-DE" });
  const learnerContext = await newBrowserContext(browser, { baseURL: webBase, locale: "de-DE" });
  const teacher = await teacherContext.newPage();
  const learner = await learnerContext.newPage();
  teacher.setDefaultTimeout(20_000);
  learner.setDefaultTimeout(20_000);

  try {
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const learnerSub = await currentUserSub(learner);

    const practice = await seedLearnerPracticeCourse(
      teacher,
      learner,
      `H5P Rückmeldung ${unique}`,
      false
    );
    const practiceTask = await createH5PTask(
      teacher,
      practice.unitId,
      practice.practiceModuleId,
      "Prüfe die gerade Zahl und lies anschließend die H5P-Rückmeldung."
    );
    practiceTask.contentId = await importH5P(
      teacher,
      teacherEmail,
      practice.unitId,
      practice.practiceModuleId,
      practiceTask.taskId
    );

    await learner.goto(
      `/learning/practice?course_id=${practice.courseId}&practice_module_id=${practice.practiceModuleId}`
    );
    await learner.getByRole("button", { name: /Aufgabe.*starten/ }).click();
    await expect(learner.locator(".h5p-multichoice")).toBeVisible({ timeout: 30_000 });
    await learner.getByRole("radio", { name: /Drei/ }).press("Space");
    await learner.getByRole("button", { name: /Check|Die Antworten überprüfen/ }).click();

    await expect(learner.getByText("Drei ist ungerade.")).toBeVisible();
    await expect(learner.locator("h5p-player")).toBeVisible();
    await expect(learner.getByRole("button", { name: "Weiter zur nächsten Aufgabe" })).toBeVisible();
    await expect(learner.getByRole("button", { name: "Aufgabe überspringen" })).toHaveCount(0);

    const unit = await create(teacher, "/api/teaching/units", {
      title: `H5P Fortschritt ${unique}`,
      unit_type: "modular"
    });
    const base = `/api/teaching/units/${unit.id}`;
    const phasesResponse = await teacher.request.get(`${webBase}${base}/phases`);
    await expectApiOk(phasesResponse);
    const phaseId = String((await phasesResponse.json())[0].id);
    const source = await create(teacher, `${base}/modules`, {
      title: "H5P Start",
      phase_id: phaseId,
      module_kind: "learning"
    });
    const target = await create(teacher, `${base}/modules`, {
      title: "Freigeschaltetes Ziel",
      phase_id: phaseId,
      module_kind: "learning"
    });
    await create(teacher, `${base}/modules/edges`, {
      from_module_id: source.id,
      to_module_id: target.id
    });
    const targetUpdate = await teacher.request.patch(`${webBase}${base}/modules/${target.id}`, {
      headers: apiHeaders(),
      data: { required_prereq_count: 1 }
    });
    await expectApiOk(targetUpdate);

    const learningTask = await createH5PTask(
      teacher,
      String(unit.id),
      String(source.id),
      "Erreiche die volle Punktzahl, um das Zielmodul freizuschalten."
    );
    learningTask.contentId = await importH5P(
      teacher,
      teacherEmail,
      String(unit.id),
      String(source.id),
      learningTask.taskId
    );
    const targetContent = await teacher.request.get(`${webBase}${base}/modules/${target.id}/content-target`);
    await expectApiOk(targetContent);
    await create(teacher, `${base}/sections/${(await targetContent.json()).section_id}/tasks`, {
      instruction_md: "Dieses Ziel ist erst nach dem H5P-Abschluss offen.",
      criteria: []
    });
    const course = await create(teacher, "/api/teaching/courses", {
      title: `H5P Fortschrittskurs ${unique}`,
      subject: "Testfach",
      grade_level: "Jahrgangsübergreifend",
      school_year_start: new Date().getFullYear()
    });
    await create(teacher, `/api/teaching/courses/${course.id}/modules`, { unit_id: unit.id });
    await create(teacher, `/api/teaching/courses/${course.id}/members`, { student_sub: learnerSub });

    const unitPath = `/learning/courses/${course.id}/units/${unit.id}`;
    await learner.goto(unitPath);
    await expect(learner.getByRole("button", { name: /Freigeschaltetes Ziel/ })).toBeDisabled();
    await learner.getByRole("button", { name: /H5P Start/ }).click();
    await learner.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(learner.locator(".h5p-multichoice")).toBeVisible({ timeout: 30_000 });
    await learner.getByRole("radio", { name: /Drei/ }).press("Space");
    await learner.getByRole("button", { name: /Check|Die Antworten überprüfen/ }).click();
    await expect(learner.getByText("Gespeichert (0/1).")).toBeVisible();
    await learner.goBack();
    await expect(learner.getByText("Noch nicht abgeschlossen · zuletzt 0/1 Punkte")).toBeVisible();
    await learner.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.getByRole("button", { name: /Freigeschaltetes Ziel/ })).toBeDisabled();

    await learner.getByRole("button", { name: /H5P Start/ }).click();
    await learner.getByRole("button", { name: "Aufgabe fortsetzen" }).click();
    const retry = learner.getByRole("button", { name: /Retry|Die Aufgabe wiederholen/ });
    await expect.poll(async () =>
      await retry.isVisible().catch(() => false) ||
      await learner.getByRole("radio", { name: /Vier/ }).isVisible().catch(() => false),
    { timeout: 30_000 }).toBe(true);
    if (await retry.isVisible().catch(() => false)) {
      await retry.click();
    }
    await learner.getByRole("radio", { name: /Vier/ }).press("Space");
    await learner.getByRole("button", { name: /Check|Die Antworten überprüfen/ }).click();
    await expect(learner.getByText("Gespeichert (1/1).")).toBeVisible();
    await learner.goBack();
    await expect(learner.getByText("Abgeschlossen · zuletzt 1/1 Punkte")).toBeVisible();

    await learner.getByRole("button", { name: "Erneut bearbeiten" }).click();
    const completedPlayer = learner.locator("h5p-player");
    await expect(completedPlayer).toBeVisible({ timeout: 30_000 });
    // MultiChoice intentionally offers no retry after a correct answer. Dispatching the
    // same score-bearing xAPI event exercises GUSTAV's real browser/BFF/server path.
    await completedPlayer.evaluate((player) => player.dispatchEvent(new CustomEvent("xAPI", {
      detail: {
        statement: {
          id: `later-partial-${Date.now()}`,
          verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
          result: { completion: true, score: { raw: 0, max: 1 } }
        }
      }
    })));
    await expect(learner.getByText("Gespeichert (0/1).")).toBeVisible();
    await learner.getByRole("button", { name: "← Zurück zu Modul H5P Start" }).click();
    await expect(learner.getByText("Abgeschlossen · zuletzt 0/1 Punkte")).toBeVisible();
    const preview = learner.getByRole("region", { name: "Eigene Bearbeitung zu Aufgabe 1" });
    await expect(preview.getByText("Abgeschlossen", { exact: true })).toBeVisible();
    await expect(preview.getByText("Zuletzt 0/1 Punkte erreicht.")).toBeVisible();
    await learner.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.getByRole("button", { name: /Freigeschaltetes Ziel/ })).toBeEnabled();
  } finally {
    await learnerContext.close().catch(() => undefined);
    await teacherContext.close().catch(() => undefined);
  }
});
