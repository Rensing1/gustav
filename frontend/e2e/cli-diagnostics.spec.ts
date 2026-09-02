import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { currentUserSub, login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUserProfile, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";
import {
  completeQueuedFeedbackDeterministically,
  holdProviderWorker,
  releaseProviderWorker
} from "./support/submission-finalization-fixture";

const password = e2ePassword;
const projectRoot = resolve(process.cwd(), "..");
const python = resolve(projectRoot, ".venv/bin/python");

// A newly created token is visible exactly once and must never enter a trace.
test.use({ trace: "off" });

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

function cliEnvironment(configRoot: string): NodeJS.ProcessEnv {
  const localCa = resolve(projectRoot, ".tmp/caddy-root.crt");
  return {
    ...process.env,
    GUSTAV_CONFIG_HOME: configRoot,
    ...(existsSync(localCa) ? { SSL_CERT_FILE: localCa } : {})
  };
}

function runCli(configRoot: string, args: string[], input?: string): string {
  try {
    return execFileSync(python, ["-m", "backend.tools.gustav_cli", ...args], {
      cwd: projectRoot,
      env: cliEnvironment(configRoot),
      encoding: "utf8",
      input
    });
  } catch {
    throw new Error("GUSTAV diagnostics CLI failed");
  }
}

test("@feature-acceptance read-only CLI diagnoses course, task, learner and latest submission", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("cli.diagnostics.teacher");
  const learnerEmail = e2eEmail("cli.diagnostics.learner");
  const tokenLabel = `CLI Diagnostik ${unique}`;
  const configRoot = mkdtempSync(resolve(tmpdir(), "gustav-cli-diagnostics-e2e-"));

  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUserProfile(learnerEmail, password, {
    firstName: "Ömer",
    lastName: "Şahin",
    displayName: "Ömer Şahin"
  });

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerNavigationCourse(
      teacher.page,
      learner.page,
      `CLI Diagnostik ${unique}`
    );
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const editor = learner.page.locator(
      '.learning-markdown-editor__surface [contenteditable="true"]'
    );
    await editor.fill("Router verbinden Netze; Switches verbinden Geräte im lokalen Netz.");
    await holdProviderWorker();
    try {
      await learner.page.getByRole("button", { name: "Rückmeldung einholen" }).click();
      await completeQueuedFeedbackDeterministically({
        courseId: seeded.courseId,
        taskId: seeded.taskId,
        learnerSub
      });
    } finally {
      await releaseProviderWorker();
    }

    await teacher.page.goto("/profile");
    await teacher.page.getByLabel("Tokenname").fill(tokenLabel);
    await teacher.page.getByLabel("read", { exact: true }).check();
    await teacher.page.getByLabel("write", { exact: true }).uncheck();
    await teacher.page.getByLabel("delete", { exact: true }).uncheck();
    await teacher.page.getByRole("button", { name: "CLI-Token erstellen" }).click();
    await expect(teacher.page.getByText("Token jetzt sicher kopieren")).toBeVisible();
    const rawToken = (await teacher.page.locator("code").first().textContent())?.trim();
    expect(rawToken).toBeTruthy();

    runCli(
      configRoot,
      ["auth", "configure", "--base-url", webBase, "--token-stdin"],
      `${rawToken}\n`
    );

    const course = JSON.parse(
      runCli(configRoot, [
        "diagnostics",
        "course",
        "--course-id",
        seeded.courseId,
        "--json"
      ])
    ) as { rows: Array<{ student: { sub: string; name: string } }> };
    expect(course.rows).toContainEqual(
      expect.objectContaining({
        student: expect.objectContaining({ sub: learnerSub, name: "Ömer Şahin" })
      })
    );

    const unit = JSON.parse(
      runCli(configRoot, [
        "diagnostics",
        "unit",
        "--course-id",
        seeded.courseId,
        "--unit-id",
        seeded.unitId,
        "--task-id",
        seeded.taskId,
        "--json"
      ])
    ) as {
      tasks: Array<{ id: string }>;
      rows: Array<{ student: { sub: string }; tasks: Array<{ task_id: string; has_submission: boolean }> }>;
    };
    expect(unit.tasks.map((task) => task.id)).toEqual([seeded.taskId]);
    expect(unit.rows.find((row) => row.student.sub === learnerSub)?.tasks).toEqual([
      expect.objectContaining({ task_id: seeded.taskId, has_submission: true })
    ]);

    const student = JSON.parse(
      runCli(configRoot, [
        "diagnostics",
        "student",
        "--student-sub",
        learnerSub,
        "--course-id",
        seeded.courseId,
        "--unit-id",
        seeded.unitId,
        "--json"
      ])
    ) as { student: { sub: string; name: string }; units: Array<{ id: string }> };
    expect(student.student).toEqual({ sub: learnerSub, name: "Ömer Şahin" });
    expect(student.units.map((unitRow) => unitRow.id)).toEqual([seeded.unitId]);

    const detail = JSON.parse(
      runCli(configRoot, [
        "diagnostics",
        "submission",
        "--course-id",
        seeded.courseId,
        "--unit-id",
        seeded.unitId,
        "--task-id",
        seeded.taskId,
        "--student-sub",
        learnerSub,
        "--json"
      ])
    ) as {
      submission: {
        text_body: string;
        feedback_md: string;
        analysis_json: { schema: string };
      };
      dialog: null;
    };
    expect(detail.submission.text_body).toContain("Router verbinden Netze");
    expect(detail.submission.analysis_json.schema).toBe("criteria.v2");
    expect(detail.submission.feedback_md).toContain("nachvollziehbar");
    expect(detail.dialog).toBeNull();

    await teacher.page.goto("/profile");
    const tokenRow = teacher.page.locator("form").filter({ hasText: tokenLabel });
    await tokenRow.getByRole("button", { name: "CLI-Token widerrufen" }).click();
    await expect(teacher.page.getByText("Das CLI-Token wurde widerrufen.")).toBeVisible();
  } finally {
    rmSync(configRoot, { recursive: true, force: true });
    await learner.context.close();
    await teacher.context.close();
  }
});
