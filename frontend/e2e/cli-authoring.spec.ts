import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

import { login } from "./support/auth";
import { apiHeaders } from "./support/api";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedH5pVisualSmokeUnit } from "./support/seed-data";

const password = "Passw0rd!e2e";
const projectRoot = resolve(process.cwd(), "..");
const python = resolve(projectRoot, ".venv/bin/python");

// The profile reveals a newly created CLI token exactly once. Keep this file
// out of Playwright traces so that a later assertion failure cannot persist it.
test.use({ trace: "off" });

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
    throw new Error(`GUSTAV CLI failed for: ${args.join(" ")}`);
  }
}

function firstId(output: string): string {
  const id = output.trim().split("\t", 1)[0];
  expect(id).toBeTruthy();
  return id;
}

function writeMinimalH5p(target: string): void {
  const fixture = resolve(projectRoot, "backend/tests_e2e/fixtures/h5p/minimal");
  const program = [
    "import pathlib, sys, zipfile",
    "source = pathlib.Path(sys.argv[1])",
    "target = pathlib.Path(sys.argv[2])",
    "with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:",
    "    for path in sorted(source.rglob('*')):",
    "        if path.is_file(): archive.write(path, path.relative_to(source).as_posix())"
  ].join("\n");
  execFileSync(python, ["-c", program, fixture, target], { cwd: projectRoot });
}

test("@feature-acceptance CLI authors a modular dialog unit and releases it in a course", async ({ page }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const email = `e2e_teacher_cli_${unique}@${emailDomain}`;
  const tokenLabel = `CLI E2E ${unique}`;
  const unitTitle = `CLI Dialogeinheit ${unique}`;
  const courseTitle = `CLI Kurs ${unique}`;
  const instruction = `CLI Dialogaufgabe ${unique}`;
  const configRoot = mkdtempSync(resolve(tmpdir(), "gustav-cli-e2e-"));

  await ensureTeacherUser(email, password);
  await login(page, email, password);

  try {
    await page.goto("/profile");
    await page.getByLabel("Tokenname").fill(tokenLabel);
    await page.getByLabel("read", { exact: true }).check();
    await page.getByLabel("write", { exact: true }).check();
    await page.getByLabel("delete", { exact: true }).check();
    await page.getByRole("button", { name: "CLI-Token erstellen" }).click();
    await expect(page.getByText("Token jetzt sicher kopieren")).toBeVisible();
    const rawToken = (await page.locator("code").first().textContent())?.trim();
    expect(rawToken).toBeTruthy();

    runCli(
      configRoot,
      ["auth", "configure", "--base-url", webBase, "--token-stdin"],
      `${rawToken}\n`
    );
    const unit = JSON.parse(
      runCli(configRoot, [
        "units",
        "create",
        "--title",
        unitTitle,
        "--unit-type",
        "modular",
        "--json"
      ])
    ) as { id: string };
    const phaseId = firstId(
      runCli(configRoot, ["phases", "create", "--unit-id", unit.id, "--title", "Start"])
    );
    const unitModuleId = firstId(
      runCli(configRoot, [
        "modules",
        "create",
        "--unit-id",
        unit.id,
        "--phase-id",
        phaseId,
        "--title",
        "Dialog"
      ])
    );
    const dialogPath = resolve(configRoot, "dialog.json");
    writeFileSync(
      dialogPath,
      JSON.stringify({
        partner_name: "Ada",
        partner_description_md: "Eine Lernpartnerin für Binärzahlen.",
        role_md: "Ask precise questions and do not reveal the solution.",
        learning_goal_md: "Explain binary place values.",
        opening_message_md: "Wie kann ich dir bei Binärzahlen helfen?",
        response_mode: "hybrid",
        max_rounds: 4,
        closing_prompt_md: null
      }),
      "utf8"
    );
    runCli(configRoot, [
      "tasks",
      "create",
      "--unit-id",
      unit.id,
      "--module-id",
      unitModuleId,
      "--instruction-md",
      instruction,
      "--kind",
      "dialog",
      "--dialog-config",
      dialogPath
    ]);

    const practiceModuleId = firstId(
      runCli(configRoot, [
        "modules",
        "create",
        "--unit-id",
        unit.id,
        "--phase-id",
        phaseId,
        "--title",
        "Wiederholen",
        "--module-kind",
        "practice"
      ])
    );
    runCli(configRoot, [
      "module-edges",
      "create",
      "--unit-id",
      unit.id,
      "--from",
      unitModuleId,
      "--to",
      practiceModuleId
    ]);
    const nativeTaskId = firstId(
      runCli(configRoot, [
        "tasks",
        "create",
        "--unit-id",
        unit.id,
        "--module-id",
        practiceModuleId,
        "--instruction-md",
        "Erkläre den TDD-Zyklus.",
        "--criterion",
        "Die drei Phasen werden korrekt erklärt.",
        "--teacher-context-md",
        "Achte auf Rot, Grün und Refactoring.",
        "--model-solution-md",
        "Zuerst scheitert der Test, dann wird er minimal erfüllt und anschließend verbessert."
      ])
    );
    runCli(configRoot, [
      "tasks",
      "edit",
      nativeTaskId,
      "--unit-id",
      unit.id,
      "--module-id",
      practiceModuleId,
      "--model-solution-md",
      "Rot zeigt die Lücke, Grün schließt sie und Refactoring verbessert den Entwurf."
    ]);
    const h5pTaskId = firstId(
      runCli(configRoot, [
        "tasks",
        "create",
        "--unit-id",
        unit.id,
        "--module-id",
        practiceModuleId,
        "--instruction-md",
        "Bearbeite die H5P-Wiederholung.",
        "--kind",
        "h5p"
      ])
    );
    const h5pPath = resolve(configRoot, "minimal.h5p");
    writeMinimalH5p(h5pPath);
    runCli(configRoot, [
      "h5p",
      "import",
      "--unit-id",
      unit.id,
      "--module-id",
      practiceModuleId,
      "--task-id",
      h5pTaskId,
      "--file",
      h5pPath,
      "--json"
    ]);
    const practiceTasks = JSON.parse(
      runCli(configRoot, [
        "tasks",
        "list",
        "--unit-id",
        unit.id,
        "--module-id",
        practiceModuleId,
        "--json"
      ])
    ) as Array<{
      id: string;
      kind: string;
      teacher_context_md: string | null;
      model_solution_md: string | null;
      h5p: { content_id: string } | null;
    }>;
    expect(practiceTasks).toHaveLength(2);
    expect(practiceTasks.find((task) => task.id === nativeTaskId)).toMatchObject({
      kind: "native",
      teacher_context_md: "Achte auf Rot, Grün und Refactoring.",
      model_solution_md: "Rot zeigt die Lücke, Grün schließt sie und Refactoring verbessert den Entwurf."
    });
    expect(practiceTasks.find((task) => task.id === h5pTaskId)?.h5p?.content_id).toBeTruthy();
    const readableModules = runCli(configRoot, ["modules", "list", "--unit-id", unit.id]);
    expect(readableModules).toContain("practice");
    const course = JSON.parse(
      runCli(configRoot, [
        "courses",
        "create",
        "--title",
        courseTitle,
        "--subject",
        "Informatik",
        "--grade-level",
        "10",
        "--school-year-start",
        String(new Date().getFullYear()),
        "--json"
      ])
    ) as { id: string };
    const courseModule = JSON.parse(
      runCli(configRoot, [
        "course-modules",
        "add",
        "--course-id",
        course.id,
        "--unit-id",
        unit.id,
        "--json"
      ])
    ) as { id: string };
    const sections = JSON.parse(
      runCli(configRoot, [
        "course-sections",
        "list",
        "--course-id",
        course.id,
        "--module-id",
        courseModule.id,
        "--json"
      ])
    ) as Array<{ id: string }>;
    expect(sections.length).toBeGreaterThan(0);
    runCli(configRoot, [
      "course-sections",
      "release",
      "--course-id",
      course.id,
      "--module-id",
      courseModule.id,
      "--section-id",
      sections[0].id,
      "--json"
    ]);

    await page.goto(`/teaching/units/${unit.id}/nodes/${unitModuleId}`);
    await expect(page.getByText(instruction, { exact: true })).toBeVisible();
    await page.goto(`/teaching/courses/${course.id}?course=1`);
    await expect(page.getByRole("heading", { name: courseTitle, exact: true })).toBeVisible();
    await expect(page.getByText(unitTitle, { exact: true })).toBeVisible();

    await page.goto("/profile");
    const tokenRow = page.locator("form").filter({ hasText: tokenLabel });
    await tokenRow.getByRole("button", { name: "CLI-Token widerrufen" }).click();
    await expect(page.getByText("Das CLI-Token wurde widerrufen.")).toBeVisible();
  } finally {
    rmSync(configRoot, { recursive: true, force: true });
  }
});

test("@feature-acceptance browser cookie flow persists H5P editor JSON", async ({ page, browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_h5p_editor_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_h5p_editor_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  await login(page, teacherEmail, password);

  const learnerContext = await browser.newContext({ baseURL: webBase });
  const learnerPage = await learnerContext.newPage();
  try {
    await login(learnerPage, learnerEmail, password);
    const seeded = await seedH5pVisualSmokeUnit(page, learnerPage, `Editor JSON ${unique}`);
    await page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.sectionId}`);
    await page.getByRole("button", { name: "H5P-Aufgabe" }).click();
    await expect(page.locator('[data-h5p-task-editor="true"]')).toBeVisible();

    const endpoint = `/api/teaching/units/${seeded.unitId}/sections/${seeded.sectionId}/tasks/${seeded.taskId}/h5p`;
    const saveResponse = await page.request.post(`${webBase}${endpoint}/save`, {
      headers: apiHeaders(`/teaching/units/${seeded.unitId}`),
      data: {
        library: "H5P.AdvancedText 1.1",
        params: {
          params: { text: `<p>Editor JSON ${unique}</p>` },
          metadata: { title: `Editor JSON ${unique}` }
        }
      }
    });
    expect(saveResponse.status(), await saveResponse.text()).toBe(200);
    const saved = await saveResponse.json() as { content_id: string };
    expect(saved.content_id).toBeTruthy();

    const modelResponse = await page.request.get(`${webBase}${endpoint}/editor-model`);
    expect(modelResponse.status()).toBe(200);
    const model = await modelResponse.json() as { library: string; params: { text: string } };
    expect(model.library).toBe("H5P.AdvancedText 1.1");
    expect(model.params.text).toContain(`Editor JSON ${unique}`);

    await page.reload();
    await page.getByRole("button", { name: "H5P-Aufgabe" }).click();
    await expect(page.locator('[data-h5p-task-editor="true"]')).toHaveAttribute(
      "data-content-id",
      String(saved.content_id)
    );
  } finally {
    await learnerContext.close();
  }
});
