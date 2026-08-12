import { expect, test, type Browser } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { login } from "./support/auth";
import { webBase } from "./support/e2e-env";

const practiceFeedback = /Sicher beherrscht|Teilweise beherrscht|Noch nicht ausreichend/;

type FixtureState = {
  status: string;
  course_id: string;
  unit_id: string;
  h5p_content_id: string;
  module_ids: Record<string, string>;
  section_ids: Record<string, string>;
  task_ids: Record<string, string>;
  dialog_session_id: string;
};

type EditorMaterial = {
  kind: string;
  mime_type: string | null;
  alt_text: string | null;
};

type EditorTask = {
  id: string;
  kind: string;
  max_attempts: number | null;
  teacher_context_md: string | null;
  h5p: { content_id: string | number } | null;
};

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required; run make dev-accounts first`);
  return value;
}

function fixtureState(): FixtureState {
  const statePath = path.resolve(process.cwd(), "..", ".tmp", "dev-accounts-state.json");
  if (!existsSync(statePath)) throw new Error("Dev account state is missing; run make dev-accounts first");
  const state = JSON.parse(readFileSync(statePath, "utf8")) as FixtureState;
  if (state.status !== "complete") throw new Error("Dev account fixture is incomplete; run make reset-dev-accounts");
  return state;
}

async function authenticatedPage(browser: Browser, email: string, password: string) {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: false });
  const page = await context.newPage();
  await login(page, email, password);
  return { context, page };
}

test("@dev-accounts exposes the complete modular browser landscape to both personas", async ({ browser }) => {
  test.skip(process.env.RUN_DEV_ACCOUNTS !== "1", "opt-in local persona smoke");
  test.setTimeout(300_000);

  const state = fixtureState();
  const teacher = await authenticatedPage(
    browser,
    requiredEnv("DEV_TEACHER_EMAIL"),
    requiredEnv("DEV_TEACHER_PASSWORD")
  );
  const learner = await authenticatedPage(
    browser,
    requiredEnv("DEV_STUDENT_EMAIL"),
    requiredEnv("DEV_STUDENT_PASSWORD")
  );

  try {
    const teacherMe = await teacher.page.request.get(`${webBase}/api/me`);
    expect(teacherMe.ok()).toBeTruthy();
    expect((await teacherMe.json()).roles).toContain("teacher");
    const learnerMe = await learner.page.request.get(`${webBase}/api/me`);
    expect(learnerMe.ok()).toBeTruthy();
    expect((await learnerMe.json()).roles).toContain("student");

    await teacher.page.goto(`/teaching/units/${state.unit_id}`);
    await expect(teacher.page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeVisible();
    await expect(teacher.page.locator(".teacher-flow-phase-band__label")).toHaveCount(3);

    const authorGraphResponse = await teacher.page.request.get(
      `${webBase}/api/teaching/units/${state.unit_id}/modules/graph`
    );
    expect(authorGraphResponse.ok()).toBeTruthy();
    const authorGraph = await authorGraphResponse.json();
    expect(authorGraph.phases).toHaveLength(3);
    expect(authorGraph.modules).toHaveLength(8);
    expect(authorGraph.edges).toHaveLength(9);
    const transfer = authorGraph.modules.find((module: { id: string }) => module.id === state.module_ids.transfer);
    expect(transfer.required_prereq_count).toBe(2);
    expect(
      authorGraph.modules.find((module: { id: string }) => module.id === state.module_ids.practice_native)
        ?.module_kind
    ).toBe("practice");
    expect(
      authorGraph.modules.find((module: { id: string }) => module.id === state.module_ids.practice_h5p)
        ?.module_kind
    ).toBe("practice");

    const materials: EditorMaterial[] = [];
    const tasks: EditorTask[] = [];
    for (const sectionId of Object.values(state.section_ids)) {
      const materialsResponse = await teacher.page.request.get(
        `${webBase}/api/teaching/units/${state.unit_id}/sections/${sectionId}/materials`
      );
      expect(materialsResponse.ok()).toBeTruthy();
      materials.push(...((await materialsResponse.json()) as EditorMaterial[]));
      const tasksResponse = await teacher.page.request.get(
        `${webBase}/api/teaching/units/${state.unit_id}/sections/${sectionId}/tasks`
      );
      expect(tasksResponse.ok()).toBeTruthy();
      tasks.push(...((await tasksResponse.json()) as EditorTask[]));
    }
    expect(new Set(tasks.map((task) => task.kind))).toEqual(
      new Set(["native", "visual", "scratch", "calliope", "filius", "h5p", "dialog"])
    );
    expect(materials.some((material) => material.kind === "markdown")).toBeTruthy();
    expect(materials.some((material) => material.mime_type === "image/png" && material.alt_text)).toBeTruthy();
    expect(materials.some((material) => material.mime_type === "application/pdf")).toBeTruthy();
    const h5pTask = tasks.find((task) => task.kind === "h5p");
    expect(String(h5pTask?.h5p?.content_id)).toBe(state.h5p_content_id);
    const practiceNative = tasks.find((task) => task.id === state.task_ids.practice_native_task);
    expect(practiceNative?.teacher_context_md).toBeTruthy();
    const practiceH5p = tasks.find((task) => task.id === state.task_ids.practice_h5p_task);
    expect(String(practiceH5p?.h5p?.content_id)).toBe(state.h5p_content_id);
    const transferTask = tasks.find((task) => task.id === state.task_ids.transfer_native);
    expect(transferTask?.max_attempts).toBe(3);
    expect(transferTask?.teacher_context_md).toBeTruthy();

    await learner.page.goto(`/learning/courses/${state.course_id}/units/${state.unit_id}`);
    await expect(learner.page).toHaveTitle(/Digitale Systeme untersuchen/);
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();

    const learnerGraphResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${state.course_id}/units/${state.unit_id}/modules/graph`
    );
    expect(learnerGraphResponse.ok()).toBeTruthy();
    const learnerGraph = await learnerGraphResponse.json();
    const statusById = new Map<string, string>(
      learnerGraph.modules.map((module: { id: string; status: string }) => [module.id, module.status])
    );
    expect(statusById.get(state.module_ids.start)).toBe("done");
    for (const key of ["analysis", "programming", "interactive"]) {
      expect(statusById.get(state.module_ids[key])).toBe("open");
    }
    expect(statusById.get(state.module_ids.practice_native)).toBe("open");
    expect(statusById.get(state.module_ids.practice_h5p)).toBe("open");
    expect(statusById.get(state.module_ids.transfer)).toBe("locked");
    expect(statusById.get(state.module_ids.finish)).toBe("locked");

    await learner.page.goto(
      `/learning/courses/${state.course_id}/units/${state.unit_id}?module=${state.module_ids.interactive}&task=${state.task_ids.h5p}`
    );
    await expect(learner.page.locator("h5p-player")).toBeVisible({ timeout: 30_000 });

    await learner.page.goto(
      `/learning/courses/${state.course_id}/units/${state.unit_id}?module=${state.module_ids.interactive}&task=${state.task_ids.dialog}`
    );
    await expect(learner.page.getByRole("region", { name: "KI-Dialog" })).toBeVisible();
    await expect(learner.page.getByText("Ich möchte untersuchen, wie Eingaben die Ausgabe eines Systems beeinflussen.")).toBeVisible();
    await expect(learner.page.getByRole("region", { name: "Dialog fortsetzen" })).toBeVisible();

    await learner.page.goto("/learning/practice");
    const staleSessionEnd = learner.page.getByRole("button", { name: "Sitzung beenden" });
    if (await staleSessionEnd.isVisible()) {
      await staleSessionEnd.click();
    }

    await learner.page.goto(
      `/learning/practice?course_id=${state.course_id}&practice_module_id=${state.module_ids.practice_native}`
    );
    await expect(learner.page.getByText(/Grundlagen wiederholen/)).toBeVisible();
    await learner.page.getByLabel("Modus").selectOption("exam");
    await learner.page.getByRole("button", { name: "Übung starten" }).click();
    await learner.page.getByLabel("Deine Antwort").fill(
      "Bei einer Suchmaschine ist der Suchbegriff die Eingabe, die Suche die Verarbeitung und die Trefferliste die Ausgabe."
    );
    await learner.page.getByRole("button", { name: "Antwort zur Auswertung senden" }).click();
    await expect(learner.page.getByRole("heading", { name: practiceFeedback })).toBeVisible({ timeout: 90_000 });
    await learner.page.reload();
    await expect(learner.page.getByRole("heading", { name: practiceFeedback })).toBeVisible();
    await learner.page.getByRole("button", { name: "Musterlösung anzeigen" }).click();
    await expect(learner.page.getByRole("heading", { name: "Musterlösung" })).toBeVisible();
    await learner.page.getByRole("button", { name: "Sitzung beenden" }).click();

    await learner.page.goto(
      `/learning/practice?course_id=${state.course_id}&practice_module_id=${state.module_ids.practice_h5p}`
    );
    await expect(learner.page.getByText(/Interaktiv wiederholen/)).toBeVisible();
    await learner.page.getByLabel("Modus").selectOption("exam");
    await learner.page.getByRole("button", { name: "Übung starten" }).click();
    const practicePlayer = learner.page.locator("h5p-player");
    await expect(practicePlayer).toBeVisible({ timeout: 30_000 });
    await practicePlayer.evaluate((element) => {
      element.dispatchEvent(new CustomEvent("xAPI", {
        detail: {
          statement: {
            id: `dev_practice_${Date.now()}`,
            verb: { id: "http://adlnet.gov/expapi/verbs/completed" },
            result: { completion: true, score: { raw: 1, max: 1 } }
          }
        }
      }));
    });
    await expect(learner.page.getByRole("heading", { name: practiceFeedback })).toBeVisible({ timeout: 30_000 });
    await learner.page.reload();
    await expect(learner.page.getByRole("heading", { name: practiceFeedback })).toBeVisible();
    await expect(learner.page.getByRole("button", { name: "Musterlösung anzeigen" })).toHaveCount(0);
    await learner.page.getByRole("button", { name: "Sitzung beenden" }).click();

    await teacher.page.goto(`/diagnostics/courses/${state.course_id}`);
    await expect(teacher.page.getByRole("heading", { name: "GUSTAV Browser-Test" })).toBeVisible();
    await expect(teacher.page.locator("tbody tr")).toHaveCount(1);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
