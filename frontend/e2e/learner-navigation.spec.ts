import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import {
  expectLearnerMaterialContrast,
  expectLearnerTaskTheme,
  expectNoViewportOverflow,
  expectWorkspaceMeasure
} from "./support/layout-sanity";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance follows graph, reading, task and feedback as one authenticated learning path", async ({ browser }) => {
  test.setTimeout(300_000);
  const unique = Date.now();
  const teacherEmail = `navigation_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `navigation_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Lernweg ${unique}`);

    await learner.page.setViewportSize({ width: 1440, height: 900 });
    await learner.page.goto("/learning");
    await expectWorkspaceMeasure(learner.page, 1280);
    await learner.page.goto(`/learning/courses/${seeded.courseId}`);
    await expectWorkspaceMeasure(learner.page, 1280);
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expectWorkspaceMeasure(learner.page, 1280);
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));
    await expect(learner.page.getByText("Dieses Material ist beim ersten Lesen vollständig geöffnet.")).toBeVisible();

    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}&task=${seeded.taskId}$`)
    );
    await expect(learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" })).toBeVisible();
    await expectNoViewportOverflow(learner.page);
    await expect(learner.page.locator(".learning-markdown-editor__toolbar")).toBeVisible();
    await expectLearnerTaskTheme(learner.page, "light");
    const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const book = learner.page.getByRole("complementary", { name: "Aufgabe und Kontext" });
    await expect(book.getByRole("heading", { name: "Materialien" })).toBeVisible();
    await expect(book.getByText("Dieses Material ist beim ersten Lesen vollständig geöffnet.")).toBeVisible();
    const secondMaterial = book.getByRole("button", {
      name: `${seeded.secondMaterialTitle} ein- oder ausklappen`
    });
    await expect(secondMaterial).toHaveAttribute("aria-expanded", "false");
    await secondMaterial.click();
    await expect(secondMaterial).toHaveAttribute("aria-expanded", "true");
    await expect(book.getByText("Dieses zweite Modulmaterial beginnt in der Arbeitsfläche eingeklappt.")).toBeVisible();

    await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
    await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
    await expectLearnerTaskTheme(learner.page, "dark");
    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expectNoViewportOverflow(learner.page);
    await expectLearnerTaskTheme(learner.page, "dark");
    await learner.page.setViewportSize({ width: 1280, height: 900 });
    await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
    await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "light");

    const answerFormat = learner.page.getByRole("group", { name: "Antwortform" });
    const textEditor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await expect(answerFormat.getByRole("radio", { name: "Text schreiben" })).toBeChecked();
    await textEditor.fill("Dieser Entwurf bleibt beim Wechsel erhalten.");

    await answerFormat.getByRole("radio", { name: "Text schreiben" }).focus();
    await learner.page.keyboard.press("ArrowRight");
    await expect(answerFormat.getByRole("radio", { name: "Datei hochladen" })).toBeChecked();
    await learner.page.getByLabel("Datei auswählen").setInputFiles({
      name: "beleg.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n%%EOF\n")
    });
    await expect(learner.page.getByText("beleg.pdf")).toBeVisible();

    await answerFormat.getByText("Text schreiben", { exact: true }).click();
    await expect(answerFormat.getByRole("radio", { name: "Text schreiben" })).toBeChecked();
    await expect(textEditor).toContainText("Dieser Entwurf bleibt beim Wechsel erhalten.");
    await answerFormat.getByText("Datei hochladen", { exact: true }).click();
    await expect(answerFormat.getByRole("radio", { name: "Datei hochladen" })).toBeChecked();
    await expect(learner.page.getByText("beleg.pdf")).toBeVisible();
    await expect(learner.page.getByRole("group", { name: "Antwortform" })).toHaveCount(1);

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    const landscapeIpadLayout = await workbench.evaluate((workspace) => {
      const desk = workspace.querySelector(".learner-task-workbench__desk");
      const context = workspace.querySelector('[data-work-surface="materials"]');
      const task = workspace.querySelector('[data-work-surface="task"]');
      if (!(desk instanceof HTMLElement) || !(context instanceof HTMLElement) || !(task instanceof HTMLElement)) {
        throw new Error("learner task surfaces are incomplete");
      }
      return {
        columns: getComputedStyle(desk).gridTemplateColumns,
        contextDisplay: getComputedStyle(context).display,
        taskDisplay: getComputedStyle(task).display
      };
    });
    expect(landscapeIpadLayout.columns.split(" ")).toHaveLength(2);
    expect(landscapeIpadLayout.contextDisplay).not.toBe("none");
    expect(landscapeIpadLayout.taskDisplay).not.toBe("none");
    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.page.getByRole("region", { name: "Laufende Aufgabe" })).toHaveCount(0);
    await expect(learner.page.getByText("Entwurf geöffnet")).toHaveCount(0);
    await expect(learner.page.getByRole("button", { name: "Zurück zum Entwurf" })).toHaveCount(0);

    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expectNoViewportOverflow(learner.page);
    await learner.page.setViewportSize({ width: 820, height: 1180 });
    await learner.page.evaluate(({ taskId, moduleId }) => {
      const workspaceKey = Object.keys(window.sessionStorage).find(
        (key) => key.startsWith("gustav.learning.workspace:") && key.endsWith(":tab")
      );
      if (!workspaceKey) throw new Error("learner workspace tab state missing");
      const staleState = JSON.parse(window.sessionStorage.getItem(workspaceKey) ?? "{}") as Record<string, unknown>;
      staleState.surface = "graph";
      staleState.activeTask = {
        itemKey: `task:${taskId}`,
        taskId,
        moduleId,
        status: "editing",
        editorMode: "text"
      };
      window.sessionStorage.setItem(workspaceKey, JSON.stringify(staleState));
    }, { taskId: seeded.taskId, moduleId: seeded.graphModuleId });
    await learner.page.reload();
    await expect(learner.page.getByRole("region", { name: "Laufende Aufgabe" })).toHaveCount(0);
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(textEditor).toContainText("Dieser Entwurf bleibt beim Wechsel erhalten.");

    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await learner.page.getByRole("button", { name: /Quellen/ }).click();
    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const materialsSwitch = workbench.getByRole("button", { name: "Materialien", exact: true });
    await materialsSwitch.click();
    await expect(materialsSwitch).toHaveAttribute("aria-pressed", "true");
    await book.getByRole("button", { name: "Modul Quellen ein- oder ausklappen" }).click();
    const contextImage = book.getByRole("img", { name: seeded.contextImageAltText });
    await expect(contextImage).toBeVisible();
    await expect.poll(() => contextImage.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    await expect(book.getByRole("button", { name: "Modul Quellen schließen" })).toBeVisible();
    await expect(book.getByRole("button", { name: "Modul Grundlagen schließen" })).toHaveCount(0);
    await expectLearnerMaterialContrast(learner.page);

    await book.getByRole("button", { name: "Modul Quellen schließen" }).click();
    await expect(book.getByRole("heading", { name: "Quellen" })).toHaveCount(0);
    const undo = book.getByRole("status");
    await expect(undo).toContainText("Modul „Quellen“ geschlossen.");
    await undo.getByRole("button", { name: "Rückgängig" }).click();
    await expect(contextImage).toBeVisible();

    await workbench.getByRole("button", { name: "Aufgabe", exact: true }).click();
    await expect(textEditor).toContainText("Dieser Entwurf bleibt beim Wechsel erhalten.");
    await answerFormat.getByText("Datei hochladen", { exact: true }).click();
    await expect(learner.page.getByText("beleg.pdf")).toHaveCount(0);
    await expect(learner.page.getByLabel("Datei auswählen")).toHaveValue("");

    await answerFormat.getByText("Text schreiben", { exact: true }).click();
    await textEditor.fill("Digitale Kommunikation braucht klare Regeln, weil Grundrechte auch online gelten.");
    await learner.page.getByRole("button", { name: "Rückmeldung einholen" }).click();

    const feedbackStatus = workbench.locator(".learning-task-feedback-status");
    await expect(feedbackStatus.getByRole("status")).toContainText("Rückmeldung wird erstellt");
    await expect(learner.page.locator(".learning-task-feedback-status")).toHaveCount(1);
    await expect(feedbackStatus.getByRole("status")).toContainText("Rückmeldung ist bereit", { timeout: 120_000 });
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}&task=${seeded.taskId}$`)
    );
    const responseGroup = workbench.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    await expect(responseGroup).toBeVisible();
    await expect(responseGroup.locator("details").filter({ hasText: "Rückmeldung" }).first()).toHaveAttribute("open", "");
    await expect(textEditor).toHaveAttribute("contenteditable", "true");

    await textEditor.fill("Digitale Kommunikation braucht klare und überprüfbare Regeln.");
    await expect(responseGroup).toBeVisible();
    await expect(learner.page.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
    await expect(learner.page.getByText("Für diese Fassung zuerst Rückmeldung einholen.").first()).toBeVisible();
    await learner.page.getByRole("button", { name: "Rückmeldung erneut einholen" }).click();
    await expect(feedbackStatus.getByRole("status")).toContainText("Rückmeldung wird erstellt");
    await expect(feedbackStatus.getByRole("status")).toContainText("Rückmeldung ist bereit", { timeout: 120_000 });
    await expect(learner.page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();

    await learner.page.goto(
      `/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}&panel=result`
    );
    const directResponseGroup = learner.page.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    await expect(directResponseGroup).toBeVisible();
    await expect(directResponseGroup.locator("details").last()).toHaveAttribute("open", "");
    await expect(learner.page.getByRole("button", { name: "Meine Abgabe" })).toHaveCount(0);

    const directAnswerFormat = learner.page.getByRole("group", { name: "Antwortform" });
    await directAnswerFormat.getByText("Datei hochladen", { exact: true }).click();
    const uploadInput = learner.page.getByLabel("Datei auswählen");
    await uploadInput.setInputFiles({
      name: "skizze.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGN87mPDwMDAxMDAwMDAAAASCQFz7+pmVQAAAABJRU5ErkJggg==",
        "base64"
      )
    });
    await expect(learner.page.getByRole("region", { name: "Ausgewählte Datei" })).toContainText("skizze.png");
    await learner.page.getByRole("button", { name: "Rückmeldung erneut einholen" }).click();
    await expect(uploadInput).toBeDisabled();
    await expect(feedbackStatus.getByRole("status")).toContainText("Rückmeldung wird erstellt");
    await expect(feedbackStatus.getByRole("status")).toContainText("Rückmeldung ist bereit", { timeout: 120_000 });
    await expect(learner.page.getByRole("region", { name: "Bisherige Datei" })).toContainText("Aktuelle Datei");
    await expect(uploadInput).toHaveValue("");
    await expect(directResponseGroup.getByRole("img", { name: "Abgabevorschau" })).toBeVisible();

    await expect(learner.page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
    await learner.page.getByRole("button", { name: "Endgültig abgeben" }).click();
    await expect(feedbackStatus.getByRole("status")).toContainText("Aufgabe abgegeben", { timeout: 120_000 });
    await expect(uploadInput).toBeDisabled();

    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.page.getByRole("region", { name: "Laufende Aufgabe" })).toHaveCount(0);
    await expect(learner.page.getByText("Aufgabe wird weiterbearbeitet.")).toHaveCount(0);

    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.page.getByRole("button", { name: "Erneut bearbeiten" }).click();
    await expect(learner.page.getByLabel("Datei auswählen")).toBeEnabled();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
