import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { apiHeaders } from "./support/api";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { countGermanSentences } from "./support/german-sentence-count";
import { expectNoViewportOverflow, expectWorkspaceMeasure } from "./support/layout-sanity";
import { seedLearnerPracticeCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";
const projectRoot = resolve(process.cwd(), "..");
const python = resolve(projectRoot, ".venv/bin/python");

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: false });
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

const feedbackHeading = /Sicher beantwortet|Teilweise beantwortet|Noch nicht sicher/;

test("@feature-acceptance teacher authors and learner completes native and H5P practice", async ({ browser }) => {
  test.setTimeout(300_000);
  const unique = Date.now();
  const teacherEmail = `practice_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `practice_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerPracticeCourse(
      teacher.page,
      learner.page,
      `Practice ${unique}`,
      false
    );

    await teacher.page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.practiceModuleId}`);
    await teacher.page.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    let createForm = teacher.page.getByTestId("teacher-node-editor-create-slot");
    await createForm.locator(
      '[contenteditable="true"][aria-label="Anweisung & Beschreibung"]'
    ).fill(
      "Erkläre, warum ein Test zuerst rot sein soll."
    );
    await createForm.getByLabel("Kriterium 1", { exact: true }).fill(
      "Die Antwort erklärt den Zweck eines zunächst fehlschlagenden Tests."
    );
    await createForm.getByText("Weitere Einstellungen", { exact: true }).click();
    await createForm.getByLabel("Lehrkraft-Kontext").fill(
      "Bewerten Sie, ob die Antwort den beobachtbaren TDD-Zyklus erklärt. Formulieren Sie die Rückmeldung als genau einen kurzen Satz ohne Überschriften."
    );
    await createForm.getByLabel("Musterlösung").fill(
      "Ein zunächst roter Test beweist, dass er die noch fehlende Funktion wirklich prüft."
    );
    await createForm.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    await expect(teacher.page.getByText("Aufgabe angelegt.")).toBeVisible();
    await expect.poll(async () => {
      const response = await teacher.page.request.get(
        `${webBase}/api/teaching/units/${seeded.unitId}/modules/${seeded.practiceModuleId}/tasks`
      );
      if (!response.ok()) return false;
      const tasks = await response.json() as Array<{ instruction_md: string }>;
      return tasks.some((task) => task.instruction_md === "Erkläre, warum ein Test zuerst rot sein soll.");
    }).toBe(true);

    await teacher.page.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();
    createForm = teacher.page.getByTestId("teacher-node-editor-create-slot");
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

    await learner.page.goto(
      `/learning/practice?course_id=${seeded.courseId}&practice_module_id=${seeded.practiceModuleId}`
    );
    await expect(learner.page.getByRole("heading", { name: "Üben" })).toBeVisible();
    const accountControl = learner.page.locator(".account-trigger");
    const stackMetadata = learner.page.locator(".practice-stack-card small");
    for (const viewport of [
      { name: "desktop", width: 1440, height: 900, columns: 2 },
      { name: "tablet", width: 1024, height: 768, columns: 1 },
      { name: "mobile", width: 390, height: 844, columns: 1 }
    ]) {
      await learner.page.setViewportSize({ width: viewport.width, height: viewport.height });
      await expectNoViewportOverflow(learner.page);
      await expectWorkspaceMeasure(learner.page, 1280);
      const columns = await learner.page.locator(".practice-selection__form").evaluate((element) =>
        getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length
      );
      expect(columns).toBe(viewport.columns);
      await expect(learner.page).toHaveScreenshot(`practice-selection-light-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl, stackMetadata]
      });
    }
    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
    await expect(learner.page).toHaveScreenshot("practice-selection-dark-tablet.png", {
      animations: "disabled",
      caret: "hide",
      mask: [accountControl, stackMetadata]
    });
    await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
    await learner.page.setViewportSize({ width: 1440, height: 900 });
    await learner.page.getByRole("button", { name: /Aufgaben starten/ }).click();
    const sessionPositionHeading = learner.page.locator(".practice-session__topline h2");
    await expect(sessionPositionHeading).toBeVisible();
    const h5pContexts = new Set<string>();
    let nativePresentations = 0;
    let h5pPresentations = 0;

    for (let step = 0; step < 4; step += 1) {
      const activeResponse = await learner.page.request.get(
        `${webBase}/api/learning/practice/sessions/active`
      );
      if (activeResponse.status() === 204) break;
      expect(activeResponse.ok(), await activeResponse.text()).toBe(true);
      const active = await activeResponse.json() as {
        current_item: { kind: "native" | "h5p"; presentation_number: number; criteria?: string[] };
      };
      expect(active.current_item).not.toHaveProperty("criteria");
      await expect(learner.page.getByText(/^Kriterien:/)).toHaveCount(0);
      await expectNoViewportOverflow(learner.page);
      await expectWorkspaceMeasure(learner.page, 1280);
      const sessionColumns = await learner.page.locator(".practice-session__layout").evaluate((element) =>
        getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length
      );
      expect(sessionColumns).toBe(2);

      if (active.current_item.kind === "native") {
        nativePresentations += 1;
        await expect(learner.page.getByText("Erkläre, warum ein Test zuerst rot sein soll.")).toBeVisible();
        if (nativePresentations === 1) {
          await expect(learner.page).toHaveScreenshot("practice-native-answer-light-desktop.png", {
            animations: "disabled",
            caret: "hide",
            mask: [accountControl, sessionPositionHeading]
          });
        }
        await learner.page.getByLabel("Deine Antwort").fill(
          nativePresentations === 1 ? "Ich weiß es noch nicht." : "Ein roter Test weist die fehlende Funktion nach."
        );
        await learner.page.getByRole("button", { name: "Antwort prüfen" }).click();
        await expect(learner.page.getByRole("heading", { name: feedbackHeading })).toBeVisible({ timeout: 60_000 });
        const feedbackBody = learner.page.locator(".practice-feedback__body");
        await expect(feedbackBody).toBeVisible();
        await expect(feedbackBody.locator("strong")).toHaveCount(0);
        const feedbackText = (await feedbackBody.innerText()).trim();
        expect(feedbackText.length).toBeGreaterThan(0);
        expect(countGermanSentences(feedbackText)).toBe(1);
        if (nativePresentations === 1) {
          await feedbackBody.evaluate((element) => {
            element.textContent = "Ihre Antwort benennt den Zweck des roten Tests und kann noch genauer begründet werden.";
          });
          const feedbackDue = learner.page.locator(".practice-feedback__due");
          if (await feedbackDue.count()) {
            await feedbackDue.evaluate((element) => {
              element.textContent = "Nächste Wiederholung: später";
            });
          }
          await expect(learner.page).toHaveScreenshot("practice-feedback-light-desktop.png", {
            animations: "disabled",
            caret: "hide",
            mask: [accountControl, sessionPositionHeading]
          });
        }
        await learner.page.reload();
        await expect(learner.page.getByRole("heading", { name: feedbackHeading })).toBeVisible();
        if (active.current_item.presentation_number === 1) {
          await learner.page.getByRole("button", { name: "Musterlösung ansehen" }).click();
          await expect(learner.page.getByText(/Ein zunächst roter Test beweist/)).toBeVisible();
        }
      } else {
        h5pPresentations += 1;
        const playerShell = learner.page.locator(".h5p-task-player");
        const player = playerShell.locator("h5p-player");
        await expect(player).toBeVisible({ timeout: 30_000 });
        await expect(playerShell.getByText("Bereit.", { exact: true })).toBeVisible({ timeout: 30_000 });
        const contextId = await player.getAttribute("context-id");
        expect(contextId).toBeTruthy();
        h5pContexts.add(contextId!);
        if (h5pPresentations === 1) {
          await expect(learner.page).toHaveScreenshot("practice-h5p-light-desktop.png", {
            animations: "disabled",
            caret: "hide",
            mask: [accountControl, sessionPositionHeading]
          });
        }
        await player.evaluate((element, input) => {
          element.dispatchEvent(new CustomEvent("xAPI", {
            detail: {
              statement: {
                id: input.id,
                verb: { id: "http://adlnet.gov/expapi/verbs/completed" },
                result: {
                  completion: true,
                  score: { raw: input.raw, max: 2 }
                }
              }
            }
          }));
        }, {
          id: `practice_h5p_${unique}_${h5pPresentations}`,
          raw: active.current_item.presentation_number === 1 ? 1 : 2
        });
        await expect(learner.page.getByRole("heading", { name: feedbackHeading })).toBeVisible({ timeout: 30_000 });
        await learner.page.reload();
        await expect(learner.page.getByRole("heading", { name: feedbackHeading })).toBeVisible();
        await expect(learner.page.getByRole("button", { name: "Musterlösung ansehen" })).toHaveCount(0);
      }

      await learner.page.getByRole("button", { name: "Nächste Aufgabe" }).click();
    }

    expect(nativePresentations).toBe(2);
    expect(h5pPresentations).toBe(2);
    expect(h5pContexts.size).toBe(2);
    await expect(learner.page.getByRole("heading", { name: "Übung geschafft" })).toBeVisible();
    await expect(learner.page.getByText("2 Aufgaben bearbeitet")).toBeVisible();
    await expect(learner.page).toHaveScreenshot("practice-summary-light-desktop.png", {
      animations: "disabled",
      caret: "hide",
      mask: [accountControl, learner.page.locator(".practice-summary__due")]
    });
    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
    await expect(learner.page).toHaveScreenshot("practice-summary-dark-tablet.png", {
      animations: "disabled",
      caret: "hide",
      mask: [accountControl, learner.page.locator(".practice-summary__due")]
    });
    await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
    await learner.page.setViewportSize({ width: 1440, height: 900 });

    await learner.page.getByRole("link", { name: "Weitere Themen üben" }).click();
    const stackCheckbox = learner.page.getByRole("checkbox", { name: /Wiederholen/ });
    await stackCheckbox.focus();
    await stackCheckbox.press("Space");
    await expect(stackCheckbox).toBeChecked();
    const allTasksRadio = learner.page.getByRole("radio", { name: /Alle Aufgaben üben/ });
    await allTasksRadio.focus();
    await allTasksRadio.press("Space");
    await expect(allTasksRadio).toBeChecked();
    await learner.page.getByRole("button", { name: "2 Aufgaben starten" }).click();
    await learner.page.getByRole("button", { name: "Sitzung beenden" }).click();
    const endDialog = learner.page.getByRole("dialog", { name: "Möchtest du die Übung jetzt beenden?" });
    await expect(endDialog).toBeVisible();
    await endDialog.getByRole("button", { name: "Sitzung beenden" }).click();
    await expect(learner.page.getByRole("heading", { name: "Übung beendet" })).toBeVisible();
    await expect(learner.page.getByRole("link", { name: "Neue Übung auswählen" })).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
