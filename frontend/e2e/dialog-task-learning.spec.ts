import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { currentUserSub, login } from "./support/auth";
import { prepareCompletedDialogTurn } from "./support/dialog-session-fixture";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerDialogCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

async function expectDialogLayout(page: Page, mode: "desktop" | "tablet" | "mobile"): Promise<void> {
  const workspace = page.getByRole("region", { name: "KI-Dialog" });
  const partnerContext = workspace.getByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
  const composer = workspace.getByRole("region", { name: "Dialog fortsetzen" });

  await expect(partnerContext.getByRole("link", { name: "Pausieren" })).toBeVisible();
  await expect(partnerContext.getByRole("button", { name: "Dialog beenden" })).toBeVisible();
  await expect(partnerContext.getByRole("button", { name: "Antwort senden" })).toHaveCount(0);
  await expect(composer.getByRole("button", { name: "Antwort senden" })).toBeVisible();
  await expect(composer.getByRole("button", { name: "Dialog beenden" })).toHaveCount(0);

  const geometry = await workspace.locator(".dialog-layout").evaluate((layout) => {
    const sidebar = layout.querySelector(".dialog-sidebar");
    const main = layout.querySelector(".dialog-main");
    const transcript = layout.querySelector(".dialog-transcript");
    const message = layout.querySelector(".dialog-message");
    if (
      !(sidebar instanceof HTMLElement) ||
      !(main instanceof HTMLElement) ||
      !(transcript instanceof HTMLElement) ||
      !(message instanceof HTMLElement)
    ) {
      throw new Error("Dialog layout is incomplete");
    }
    const sidebarBox = sidebar.getBoundingClientRect();
    const mainBox = main.getBoundingClientRect();
    const transcriptBox = transcript.getBoundingClientRect();
    const messageBox = message.getBoundingClientRect();
    return {
      width: layout.getBoundingClientRect().width,
      columns: getComputedStyle(layout).gridTemplateColumns,
      direction: getComputedStyle(layout).direction,
      sidebar: { x: sidebarBox.x, y: sidebarBox.y, width: sidebarBox.width, height: sidebarBox.height },
      main: { x: mainBox.x, y: mainBox.y, width: mainBox.width, height: mainBox.height },
      messageWidth: messageBox.width,
      transcriptWidth: transcriptBox.width
    };
  });

  if (mode === "desktop") {
    expect(geometry.width, `desktop dialog geometry: ${JSON.stringify(geometry)}`).toBeGreaterThanOrEqual(1024);
    expect(
      geometry.main.x,
      `desktop dialog geometry: ${JSON.stringify(geometry)}`
    ).toBeGreaterThan(geometry.sidebar.x + geometry.sidebar.width - 1);
  } else {
    expect(geometry.main.y).toBeGreaterThan(geometry.sidebar.y + geometry.sidebar.height - 1);
  }
  if (mode === "tablet") {
    expect(geometry.width).toBeGreaterThanOrEqual(680);
    expect(geometry.width).toBeLessThan(1024);
  }
  if (mode === "mobile") {
    expect(geometry.width).toBeLessThan(680);
    expect(Math.abs(geometry.messageWidth - geometry.transcriptWidth)).toBeLessThanOrEqual(1);
  }
}

async function useWideSinglePaneLayout(page: Page): Promise<void> {
  const settingsButton = page.getByRole("button", { name: "Layout-Einstellungen" });
  await settingsButton.click();
  const settings = page.getByRole("dialog", { name: "Layout-Einstellungen" });
  const toc = settings.getByRole("checkbox", { name: "Inhaltsverzeichnis" });
  if (await toc.isChecked()) {
    await toc.uncheck();
  }
  const splitView = settings.getByRole("checkbox", { name: "Zwei Ansichten" });
  if (await splitView.isChecked()) {
    await splitView.uncheck();
  }
  const workspaceWidth = settings
    .locator(".workspace-settings-menu__field")
    .filter({ hasText: "Breite Arbeitsrahmen" })
    .locator('input[type="number"]');
  await workspaceWidth.fill("96");
  await workspaceWidth.blur();
  await settingsButton.click();
  await expect(settings).toBeHidden();
}

test("@feature-acceptance learner deliberately enters and resumes dialog completion", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `e2e_teacher_dialog_learning_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_learner_dialog_learning_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerDialogCourse(teacher.page, learner.page, `Dialog Lernen ${unique}`);

    await learner.page.setViewportSize({ width: 1600, height: 1000 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
    await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
    await expect(learner.page.getByRole("region", { name: "KI-Dialog" })).toBeVisible();
    await expect(learner.page.getByText("Welche Beobachtung möchtest du zuerst untersuchen?")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();
    await expect(learner.page.getByRole("button", { name: "Dialog beenden" })).toBeHidden();
    const initialPartnerContext = learner.page.getByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
    await expect(initialPartnerContext.getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeVisible();
    await expect(
      learner.page.getByRole("region", { name: "Dialog fortsetzen" }).getByRole("button", { name: "Antwort senden" })
    ).toBeVisible();

    const sessionId = await prepareCompletedDialogTurn({
      courseId: seeded.courseId,
      taskId: seeded.taskId,
      learnerSub
    });
    const storageKey = `gustav.learning.dialog-closing-draft:${encodeURIComponent(learnerSub)}:${seeded.courseId}:${seeded.taskId}:${sessionId}`;

    await learner.page.reload();
    await expect(learner.page.getByText("Welche Textstelle belegt diese Beobachtung?")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();
    await useWideSinglePaneLayout(learner.page);
    await expectDialogLayout(learner.page, "desktop");
    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await expectDialogLayout(learner.page, "tablet");
    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expectDialogLayout(learner.page, "mobile");
    await learner.page.setViewportSize({ width: 1600, height: 1000 });
    await expectDialogLayout(learner.page, "desktop");
    await learner.page.getByRole("button", { name: "Dialog beenden" }).click();

    const closingField = learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.");
    await expect(closingField).toBeVisible();
    const closingPartnerContext = learner.page.getByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
    const closingRegion = learner.page.getByRole("region", { name: "Abschluss vorbereiten" });
    await expect(closingPartnerContext.getByRole("link", { name: "Pausieren" })).toBeVisible();
    await expect(closingPartnerContext.getByRole("button", { name: "Dialog beenden" })).toHaveCount(0);
    await expect(closingRegion.getByRole("button", { name: "Zurück zum Dialog" })).toBeVisible();
    await expect(closingRegion.getByRole("button", { name: "Endgültig abgeben" })).toBeVisible();
    await expect(closingRegion.getByRole("link", { name: "Pausieren" })).toHaveCount(0);
    await closingField.fill("Die Auswahl der Textstellen bestimmt die Perspektive.");
    await expect(learner.page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();

    await closingPartnerContext.getByRole("link", { name: "Pausieren" }).click();
    await expect(learner.page).toHaveURL(new RegExp(`/learning/courses/${seeded.courseId}/?$`));
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.")).toHaveValue(
      "Die Auswahl der Textstellen bestimmt die Perspektive."
    );
    await learner.page.getByRole("button", { name: "Zurück zum Dialog" }).click();
    await expect(learner.page.getByLabel("Deine Antwort (1/2)")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();

    await learner.page.getByRole("button", { name: "Dialog beenden" }).click();
    await expect(learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.")).toHaveValue(
      "Die Auswahl der Textstellen bestimmt die Perspektive."
    );
    await learner.page.getByRole("button", { name: "Endgültig abgeben" }).click();

    await expect(learner.page.getByText("Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.")).toBeVisible();
    expect(await learner.page.evaluate((key) => window.sessionStorage.getItem(key), storageKey)).toBeNull();
    const sessionResponse = await learner.page.request.get(
      `${webBase}/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/dialog-sessions/${sessionId}`
    );
    expect(sessionResponse.ok(), await sessionResponse.text()).toBe(true);
    expect((await sessionResponse.json()).status).toBe("completed");
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
