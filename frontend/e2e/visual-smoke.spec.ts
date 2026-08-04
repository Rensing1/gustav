import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { currentUserSub, login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import {
  expectInteractiveSurface,
  expectNoViewportOverflow,
  expectVisiblePageShell,
  type SmokePage
} from "./support/layout-sanity";
import {
  seedH5pVisualSmokeUnit,
  seedLearnerVisualSmokeCourse,
  seedTeacherVisualSmokeUnit
} from "./support/seed-data";

const password = "Passw0rd!e2e";

const smokePages: SmokePage[] = [
  { path: "/", heading: "Anmelden" },
  { path: "/register", heading: "Registrieren" },
  { path: "/forgot-password", heading: "Passwort zurücksetzen" }
];

async function newSmokePage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({
    baseURL: webBase,
    ignoreHTTPSErrors: true
  });
  return { context, page: await context.newPage() };
}

test.describe("@visual-smoke auth shell pages", () => {
  for (const viewport of [
    { name: "desktop", width: 1280, height: 900 },
    { name: "mobile", width: 390, height: 844 }
  ]) {
    test(`render non-empty auth shells on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      for (const smokePage of smokePages) {
        await expectVisiblePageShell(page, smokePage);
      }
    });
  }
});

test.describe("@visual-smoke teacher workspace", () => {
  test("renders the modular teacher graph without empty or overflowing chrome", async ({ page }) => {
    const unique = Date.now();
    const email = `visual_teacher_${unique}@${emailDomain}`;
    await ensureTeacherUser(email, password);
    await login(page, email, password);

    const seeded = await seedTeacherVisualSmokeUnit(page, `Visual Smoke Graph ${unique}`);

    await page.goto(`/teaching/units/${seeded.unitId}`);
    await expect(page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeVisible();
    await expect(page.locator(".teacher-flow-node--module")).toHaveCount(2);
    await expectInteractiveSurface(page.locator(".teacher-flow-workspace"));
    await expectNoViewportOverflow(page);
  });
});

test.describe("@visual-smoke learner workspace", () => {
  test("@design-system renders the responsive learner orientation, work and reading surfaces", async ({ browser }) => {
    test.setTimeout(90_000);
    const unique = Date.now();
    const teacherEmail = `visual_teacher_learner_${unique}@${emailDomain}`;
    const learnerEmail = `visual_learner_${unique}@${emailDomain}`;
    await ensureTeacherUser(teacherEmail, password);
    await ensureLearnerUser(learnerEmail, password);

    const teacher = await newSmokePage(browser);
    const learner = await newSmokePage(browser);
    try {
      await login(teacher.page, teacherEmail, password);
      await login(learner.page, learnerEmail, password);
      const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, "Lernraum Referenz");

      await learner.page.setViewportSize({ width: 1920, height: 1080 });
      await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
      await expect(learner.page.getByText("Beschreibe in zwei Sätzen", { exact: false })).toBeVisible();
      await expectInteractiveSurface(learner.page.locator(".learning-unit-stage--content"));
      await expectNoViewportOverflow(learner.page);
      await learner.page.evaluate(async () => {
        await document.fonts.ready;
      });

      const accountControl = learner.page.locator(".account-trigger");
      await expect(learner.page).toHaveScreenshot("learner-orientation-light-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });

      await learner.page.getByRole("button", { name: /beginnen/i }).first().click();
      const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
      const taskSurface = workbench.getByRole("main", { name: "Bearbeitung" });
      const contextSurface = workbench.getByRole("complementary", { name: "Aufgabe und Kontext" });
      await expect(taskSurface).toBeVisible();
      await expect(contextSurface).toBeVisible();
      await expect
        .poll(() => contextSurface.locator(".learner-task-context__scroll").evaluate((surface) => surface.scrollTop))
        .toBe(0);
      const verticalGeometry = await learner.page.evaluate(() => {
        const taskHeader = document.querySelector(".learner-task-header");
        const contextHeader = document.querySelector(".learner-task-context__header");
        const workbench = document.querySelector(".learner-task-workbench");
        const context = document.querySelector(".learner-task-context");
        if (!(taskHeader instanceof HTMLElement) || !(contextHeader instanceof HTMLElement) || !(workbench instanceof HTMLElement) || !(context instanceof HTMLElement)) {
          throw new Error("learner task headers are incomplete");
        }
        return {
          taskHeaderTop: taskHeader.getBoundingClientRect().top,
          taskHeaderBottom: taskHeader.getBoundingClientRect().bottom,
          workbenchTop: workbench.getBoundingClientRect().top,
          contextTop: context.getBoundingClientRect().top,
          contextHeaderTop: contextHeader.getBoundingClientRect().top,
          taskHeaderPosition: getComputedStyle(taskHeader).position,
          contextPosition: getComputedStyle(context).position
        };
      });
      expect(verticalGeometry.contextHeaderTop).toBeGreaterThanOrEqual(verticalGeometry.taskHeaderBottom);
      const desktopGeometry = await workbench.evaluate((workspace) => {
        const context = workspace.querySelector('[data-work-surface="materials"]');
        const task = workspace.querySelector('[data-work-surface="task"]');
        if (!(context instanceof HTMLElement) || !(task instanceof HTMLElement)) {
          throw new Error("learner work surfaces are incomplete");
        }
        return {
          context: context.getBoundingClientRect().toJSON(),
          task: task.getBoundingClientRect().toJSON(),
          columns: getComputedStyle(workspace).gridTemplateColumns
        };
      });
      expect(desktopGeometry.columns.split(" ")).toHaveLength(2);
      expect(desktopGeometry.task.x).toBeGreaterThan(
        desktopGeometry.context.x + desktopGeometry.context.width - 1
      );
      await expect
        .poll(() => contextSurface.evaluate((surface) => getComputedStyle(surface).position))
        .toBe("sticky");
      await expect(learner.page).toHaveScreenshot("learner-work-light-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });

      const currentMaterial = contextSurface
        .locator(".learner-task-context__material")
        .filter({ hasText: "Grundrechte und digitale Kommunikation" });
      await currentMaterial.getByRole("button", { name: "Fokussiert lesen" }).click();
      const reader = contextSurface.getByRole("article", { name: "Kontext lesen" });
      await expect(reader).toBeVisible();
      await expect(reader.getByRole("heading", { name: "Grundrechte und digitale Kommunikation" })).toBeVisible();
      const readingMeasure = await reader.locator(".learner-context-reader__body").evaluate((body) => ({
        width: body.getBoundingClientRect().width,
        maxWidth: Number.parseFloat(getComputedStyle(body).maxWidth)
      }));
      expect(readingMeasure.width).toBeLessThanOrEqual(readingMeasure.maxWidth + 1);
      await expect(learner.page).toHaveScreenshot("learner-context-light-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });

      await learner.page.setViewportSize({ width: 1366, height: 768 });
      await expect(taskSurface).toBeVisible();
      await expect(contextSurface).toBeVisible();
      await expect(workbench.getByRole("button", { name: "Aufgabe" })).toBeHidden();
      await expectNoViewportOverflow(learner.page);
      await expect(learner.page).toHaveScreenshot("learner-context-light-1366.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });

      for (const viewport of [
        { name: "tablet", width: 1024, height: 768 },
        { name: "mobile", width: 390, height: 844 }
      ] as const) {
        await learner.page.setViewportSize({ width: viewport.width, height: viewport.height });
        await expect(workbench.getByRole("button", { name: "Aufgabe" })).toBeVisible();
        await expect(contextSurface).toBeVisible();
        await expect(taskSurface).toBeHidden();
        await expectNoViewportOverflow(learner.page);
        await expect(learner.page).toHaveScreenshot(`learner-context-light-${viewport.name}.png`, {
          animations: "disabled",
          caret: "hide",
          mask: [accountControl]
        });
      }

      await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await expect(learner.page).toHaveScreenshot("learner-context-dark-mobile.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
    } finally {
      await learner.context.close();
      await teacher.context.close();
    }
  });
});

test.describe("@visual-smoke h5p workspace", () => {
  test("renders the learner H5P task shell for a released H5P task", async ({ browser }) => {
    const unique = Date.now();
    const teacherEmail = `visual_teacher_h5p_${unique}@${emailDomain}`;
    const learnerEmail = `visual_learner_h5p_${unique}@${emailDomain}`;
    await ensureTeacherUser(teacherEmail, password);
    await ensureLearnerUser(learnerEmail, password);

    const teacher = await newSmokePage(browser);
    const learner = await newSmokePage(browser);
    try {
      await login(teacher.page, teacherEmail, password);
      await login(learner.page, learnerEmail, password);
      const seeded = await seedH5pVisualSmokeUnit(teacher.page, learner.page, `Visual Smoke ${unique}`);
      await currentUserSub(learner.page);

      await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
      await learner.page.getByRole("button", { name: /beginnen/ }).first().click();
      await expect(learner.page.getByText("Diese H5P-Aufgabe ist noch nicht bereit.")).toBeVisible();
      await expectInteractiveSurface(learner.page.locator(".learning-unit-stage--content"));
      await expectNoViewportOverflow(learner.page);
    } finally {
      await learner.context.close();
      await teacher.context.close();
    }
  });
});
