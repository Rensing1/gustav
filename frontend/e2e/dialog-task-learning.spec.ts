import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { currentUserSub, login } from "./support/auth";
import { appendTerminalDialogFailure, completeDialogFeedback, prepareCompletedDialogTurn } from "./support/dialog-session-fixture";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerDialogCourse } from "./support/seed-data";

const password = e2ePassword;

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

async function expectDialogLayout(page: Page, mode: "desktop" | "mobile"): Promise<void> {
  const workspace = page.getByRole("region", { name: "KI-Dialog" });
  const taskContext = workspace.getByRole("complementary", { name: "Aufgabe und Kontext" });
  const composer = workspace.getByRole("region", { name: "Dialog fortsetzen" });
  await expect(page.locator("#learner-task-back")).toBeVisible();
  await expect(taskContext.getByRole("button", { name: "Pausieren" })).toHaveCount(0);

  if (mode === "desktop") {
    await expect(taskContext.getByRole("button", { name: "Dialog beenden" })).toHaveCount(0);
    await expect(composer.getByRole("button", { name: "Antwort senden" })).toBeVisible();
  } else {
    await expect(taskContext).toBeHidden();
    await expect(composer).toBeVisible();
    await workspace.getByRole("button", { name: "Materialien" }).click();
    await expect(taskContext).toBeVisible();
    await expect(composer).toBeHidden();
    await workspace.getByRole("button", { name: "Aufgabe" }).click();
    await expect(composer).toBeVisible();
  }
  await expect(taskContext.getByRole("button", { name: "Antwort senden" })).toHaveCount(0);
  await expect(composer.getByRole("button", { name: "Dialog beenden" })).toBeVisible();

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
    const transcriptStyle = getComputedStyle(transcript);
    const transcriptContentWidth = transcriptBox.width
      - Number.parseFloat(transcriptStyle.paddingLeft)
      - Number.parseFloat(transcriptStyle.paddingRight);
    return {
      width: layout.getBoundingClientRect().width,
      columns: getComputedStyle(layout).gridTemplateColumns,
      direction: getComputedStyle(layout).direction,
      sidebar: { x: sidebarBox.x, y: sidebarBox.y, width: sidebarBox.width, height: sidebarBox.height },
      main: { x: mainBox.x, y: mainBox.y, width: mainBox.width, height: mainBox.height },
      messageWidth: messageBox.width,
      transcriptWidth: transcriptBox.width,
      transcriptContentWidth
    };
  });

  if (mode === "desktop") {
    expect(geometry.width, `split dialog geometry: ${JSON.stringify(geometry)}`).toBeGreaterThanOrEqual(960);
    expect(
      geometry.main.x,
      `desktop dialog geometry: ${JSON.stringify(geometry)}`
    ).toBeGreaterThan(geometry.sidebar.x + geometry.sidebar.width - 1);
  }
  if (mode === "mobile") {
    expect(geometry.width).toBeLessThan(680);
    expect(Math.abs(geometry.messageWidth - geometry.transcriptContentWidth)).toBeLessThanOrEqual(1);
  }
}

test("@feature-acceptance learner deliberately enters and resumes dialog completion", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const learnerSub = await currentUserSub(learner.page);
    const seeded = await seedLearnerDialogCourse(teacher.page, learner.page, "Dialog Lernraum Referenz");

    await learner.page.setViewportSize({ width: 1600, height: 1000 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
    await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
    await expect(learner.page.getByRole("region", { name: "KI-Dialog" })).toBeVisible();
    await expect(learner.page.getByText("Welche Beobachtung möchtest du zuerst untersuchen?")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();
    await expect(learner.page.getByRole("button", { name: "Dialog beenden" })).toBeHidden();
    const initialTaskContext = learner.page.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const initialComposer = learner.page.getByRole("region", { name: "Dialog fortsetzen" });
    const initialDialogGeometry = await learner.page.getByRole("region", { name: "KI-Dialog" }).evaluate((workspace) => {
      const sidebar = workspace.querySelector(".dialog-sidebar");
      return {
        width: workspace.getBoundingClientRect().width,
        sidebarDisplay: sidebar ? getComputedStyle(sidebar).display : null
      };
    });
    expect(initialDialogGeometry.width).toBeGreaterThanOrEqual(1152);
    expect(initialDialogGeometry.sidebarDisplay).toBe("grid");
    await expect(initialTaskContext.getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toHaveCount(0);
    await expect(initialComposer.getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeVisible();
    await expect(
      learner.page.getByRole("region", { name: "Dialog fortsetzen" }).getByRole("button", { name: "Antwort senden" })
    ).toBeVisible();

    const sessionId = await prepareCompletedDialogTurn({
      courseId: seeded.courseId,
      taskId: seeded.taskId,
      learnerSub,
      longTranscript: true
    });
    const storageKey = `gustav.learning.dialog-closing-draft:${encodeURIComponent(learnerSub)}:${seeded.courseId}:${seeded.taskId}:${sessionId}`;

    await learner.page.reload();
    await expect(learner.page.getByText("Welche Textstelle belegt diese Beobachtung?")).toBeVisible();
    await expect(learner.page.getByRole("article", { name: "Aktuelle Frage" })).toContainText(
      "Welche Textstelle belegt diese Beobachtung?"
    );
    await expect(learner.page.getByRole("region", { name: "Gesprächsfortschritt" })).toContainText("Runde 1 von 2");
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();
    const dialogSeparator = learner.page.getByRole("separator", { name: "Spaltenbreite anpassen" });
    await expectDialogLayout(learner.page, "desktop");
    await expect(dialogSeparator).toBeVisible();
    const dialogCoachGeometry = await learner.page.getByRole("region", { name: "KI-Dialog" }).evaluate((workspace) => {
      const main = workspace.querySelector(".dialog-main");
      const transcript = workspace.querySelector(".dialog-transcript");
      const composer = workspace.querySelector(".dialog-composer");
      if (!(main instanceof HTMLElement) || !(transcript instanceof HTMLElement) || !(composer instanceof HTMLElement)) {
        throw new Error("Dialogcoach layout is incomplete");
      }
      const mainBox = main.getBoundingClientRect();
      const transcriptBox = transcript.getBoundingClientRect();
      const composerBox = composer.getBoundingClientRect();
      return {
        viewportHeight: window.innerHeight,
        main: { top: mainBox.top, bottom: mainBox.bottom },
        transcript: {
          top: transcriptBox.top,
          bottom: transcriptBox.bottom,
          clientHeight: transcript.clientHeight,
          scrollHeight: transcript.scrollHeight,
          scrollTop: transcript.scrollTop
        },
        composer: { top: composerBox.top, bottom: composerBox.bottom }
      };
    });
    expect(dialogCoachGeometry.transcript.scrollHeight).toBeGreaterThan(dialogCoachGeometry.transcript.clientHeight);
    expect(
      Math.abs(
        dialogCoachGeometry.transcript.scrollHeight -
        dialogCoachGeometry.transcript.clientHeight -
        dialogCoachGeometry.transcript.scrollTop
      )
    ).toBeLessThanOrEqual(2);
    expect(dialogCoachGeometry.transcript.top).toBeGreaterThanOrEqual(dialogCoachGeometry.main.top);
    expect(dialogCoachGeometry.composer.top).toBeGreaterThanOrEqual(dialogCoachGeometry.transcript.bottom);
    expect(dialogCoachGeometry.composer.bottom).toBeLessThanOrEqual(dialogCoachGeometry.main.bottom + 1);
    expect(dialogCoachGeometry.composer.bottom).toBeLessThanOrEqual(dialogCoachGeometry.viewportHeight + 1);
    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await expectDialogLayout(learner.page, "desktop");
    await expect(dialogSeparator).toBeVisible();
    await expect(learner.page.getByRole("article", { name: "Aktuelle Frage" })).toBeVisible();
    const tabletTranscript = await learner.page.locator(".dialog-transcript").evaluate((transcript) => ({
      clientHeight: transcript.clientHeight,
      scrollHeight: transcript.scrollHeight,
      scrollTop: transcript.scrollTop
    }));
    expect(tabletTranscript.scrollHeight).toBeGreaterThan(tabletTranscript.clientHeight);
    expect(
      Math.abs(tabletTranscript.scrollHeight - tabletTranscript.clientHeight - tabletTranscript.scrollTop)
    ).toBeLessThanOrEqual(2);
    const tabletCurrentQuestion = await learner.page.getByRole("article", { name: "Aktuelle Frage" }).evaluate((article) => {
      const transcript = article.closest(".dialog-transcript");
      if (!(transcript instanceof HTMLElement)) throw new Error("Current question is outside the transcript");
      const articleBox = article.getBoundingClientRect();
      const transcriptBox = transcript.getBoundingClientRect();
      return {
        articleTop: articleBox.top,
        articleBottom: articleBox.bottom,
        transcriptTop: transcriptBox.top,
        transcriptBottom: transcriptBox.bottom
      };
    });
    expect(tabletCurrentQuestion.articleTop).toBeGreaterThanOrEqual(tabletCurrentQuestion.transcriptTop - 1);
    expect(tabletCurrentQuestion.articleBottom).toBeLessThanOrEqual(tabletCurrentQuestion.transcriptBottom + 1);
    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expectDialogLayout(learner.page, "mobile");
    await expect(dialogSeparator).toBeHidden();
    await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
    await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
    await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
    await learner.page.setViewportSize({ width: 1600, height: 1000 });
    await expectDialogLayout(learner.page, "desktop");
    await learner.page.getByRole("button", { name: "Dialog beenden" }).click();

    const closingField = learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.");
    await expect(closingField).toBeVisible();
    const closingTaskContext = learner.page.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const closingRegion = learner.page.getByRole("region", { name: "Abschluss vorbereiten" });
    await expect(closingTaskContext.getByRole("button", { name: "Pausieren" })).toHaveCount(0);
    await expect(closingTaskContext.getByRole("button", { name: "Dialog beenden" })).toHaveCount(0);
    await expect(closingRegion.getByRole("button", { name: "Zurück zum Dialog" })).toBeVisible();
    await expect(closingRegion.getByRole("button", { name: "Endgültig abgeben" })).toBeVisible();
    await expect(closingRegion.getByRole("button", { name: "Pausieren" })).toHaveCount(0);
    await closingField.fill("Die Auswahl der Textstellen bestimmt die Perspektive.");
    await expect(learner.page.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();

    await learner.page.locator("#learner-task-back").click();
    await expect(learner.page.getByRole("region", { name: "Orientieren" })).toBeVisible();
    await learner.page.reload();
    await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
    await expect(learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.")).toHaveValue(
      "Die Auswahl der Textstellen bestimmt die Perspektive."
    );
    await learner.page.getByRole("button", { name: "Zurück zum Dialog" }).click();
    await expect(learner.page.getByLabel("Deine Antwort (1/2)")).toBeVisible();
    await expect(learner.page.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeHidden();

    await appendTerminalDialogFailure(sessionId);
    await learner.page.reload();
    await expect(learner.page.getByRole("button", { name: "KI-Antwort erneut versuchen" })).toHaveCount(0);
    await expect(learner.page.getByText("Die KI-Antwort kann nicht erneut erzeugt werden.")).toBeVisible();
    await expect(learner.page.getByRole("button", { name: "Dialog beenden" })).toBeVisible();
    await expect(learner.page.getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeVisible();

    await learner.page.getByRole("button", { name: "Dialog beenden" }).click();
    await expect(learner.page.getByLabel("Fasse deine wichtigste Erkenntnis zusammen.")).toHaveValue(
      "Die Auswahl der Textstellen bestimmt die Perspektive."
    );
    await learner.page.getByRole("button", { name: "Endgültig abgeben" }).click();

    await expect(learner.page.getByText("Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.")).toBeVisible();
    await completeDialogFeedback({
      sessionId,
      feedbackMd: "Du belegst deine Einschätzung nachvollziehbar mit der Quelle."
    });
    await expect(learner.page.getByText("Rückmeldung ist bereit", { exact: true })).toBeVisible();
    const feedback = learner.page.getByRole("region", { name: "Rückmeldung zum KI-Dialog" });
    await expect(feedback).toContainText("Du belegst deine Einschätzung nachvollziehbar mit der Quelle.");
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
