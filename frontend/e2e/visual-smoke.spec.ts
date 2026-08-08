import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { currentUserSub, login } from "./support/auth";
import { apiHeaders, expectApiOk } from "./support/api";
import { makeCourseMetadataIncomplete } from "./support/course-fixture";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import {
  expectInteractiveSurface,
  expectLearnerMaterialContrast,
  expectLearnerTaskTheme,
  expectNoViewportOverflow,
  expectVisiblePageShell,
  type SmokePage
} from "./support/layout-sanity";
import {
  seedH5pVisualSmokeUnit,
  seedLearnerVisualSmokeCourse,
  seedTeacherHomeWorkStarter,
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

async function fitVisibleGraph(page: Page): Promise<void> {
  const fitButton = page.getByRole("button", { name: "Gesamtansicht" });
  // The first pass reacts to a preceding viewport/grid resize; the second uses
  // the settled canvas dimensions and therefore produces a stable reference.
  for (let pass = 0; pass < 2; pass += 1) {
    await fitButton.evaluate((button) => (button as HTMLButtonElement).click());
    await page.evaluate(() => new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    }));
  }
}

async function expectCenteredGraphContext(page: Page): Promise<void> {
  const geometryIsCentered = await page.evaluate(() => {
    const canvas = document.querySelector<HTMLElement>(".teacher-flow-workspace__canvas")?.getBoundingClientRect();
    const modules = Array.from(document.querySelectorAll<HTMLElement>(".teacher-flow-node--module"));
    if (!canvas || canvas.height < 400 || modules.length === 0) return false;
    return modules.every((module) => {
      const rect = module.getBoundingClientRect();
      return rect.top >= canvas.top + 48 && rect.bottom <= canvas.bottom - 48;
    });
  });
  expect(geometryIsCentered).toBe(true);
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
  test("@design-system renders the teacher work starter across themes and widths", async ({ page }) => {
    const unique = Date.now();
    const email = `visual_teacher_home_${unique}@${emailDomain}`;
    await ensureTeacherUser(email, password);
    await login(page, email, password);
    await seedTeacherHomeWorkStarter(page, "Visual Arbeitsstart");
    await page.goto("/teaching");
    await page.evaluate(async () => {
      await document.fonts.ready;
    });

    const accountControl = page.locator(".account-trigger");
    const updatedAt = page.locator(".teacher-home-workstarter .quiet-list-entry__meta");

    for (const viewport of [
      { name: "desktop", width: 1440, height: 900, columns: 2 },
      { name: "tablet", width: 1024, height: 768, columns: 1 },
      { name: "mobile", width: 390, height: 844, columns: 1 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await expectNoViewportOverflow(page);
      const columnCount = await page.locator(".teacher-home-workstarter__grid").evaluate((element) =>
        getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length
      );
      expect(columnCount).toBe(viewport.columns);

      await expect(page).toHaveScreenshot(`teacher-home-light-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl, updatedAt],
      });

      await page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await expect(page).toHaveScreenshot(`teacher-home-dark-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl, updatedAt],
      });
      await page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
      await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "light");
    }
  });

  test("@design-system renders the modular graph inspector and deletion dialog across themes and widths", async ({ page }) => {
    test.setTimeout(120_000);
    const unique = Date.now();
    const email = `visual_teacher_${unique}@${emailDomain}`;
    await ensureTeacherUser(email, password);
    await login(page, email, password);

    const seeded = await seedTeacherVisualSmokeUnit(page, "Visual Smoke Graph");

    await page.goto(`/teaching/units/${seeded.unitId}`);
    await expect(page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeVisible();
    await expect(page.locator(".teacher-flow-node--module")).toHaveCount(2);
    await expectInteractiveSurface(page.locator(".teacher-flow-workspace"));
    const phaseLink = page.locator(".teacher-flow-phase-band__label").first();
    const phaseHref = await phaseLink.getAttribute("href");
    expect(phaseHref).toBeTruthy();
    const phaseUrl = `/teaching/units/${seeded.unitId}${phaseHref}`;
    const phasePropertiesUrl = `${phaseUrl}&panel=phase-properties`;
    await phaseLink.click();
    const phaseContext = page.getByRole("region", { name: "Ausgewählte Phase" });
    await expect(phaseContext).toBeVisible();
    await phaseContext.getByRole("button", { name: "Eigenschaften" }).click();
    const inspector = page.getByRole("complementary", { name: "Phase bearbeiten" });
    const accountControl = page.locator(".account-trigger");
    await expect(inspector).toBeVisible();
    await page.evaluate(async () => { await document.fonts.ready; });

    for (const viewport of [
      { name: "desktop", width: 1440, height: 900 },
      { name: "tablet", width: 1024, height: 768 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.evaluate(() => window.scrollTo(0, 0));
      await expectNoViewportOverflow(page);
      if (viewport.width > 720) {
        await fitVisibleGraph(page);
        await expect(phaseLink).toBeInViewport({ ratio: 0.2 });
        if (viewport.width >= 1200) await expectCenteredGraphContext(page);
      }
      await expect(page).toHaveScreenshot(`teacher-graph-inspector-light-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: viewport.width > 720 ? [accountControl] : [],
        maxDiffPixelRatio: 0.005,
      });

      await inspector.getByRole("button", { name: "Phase löschen" }).click();
      const dialog = page.getByRole("dialog", { name: "Phase löschen" });
      await expect(dialog).toBeVisible();
      await expect(page).toHaveScreenshot(`teacher-graph-delete-light-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: viewport.width > 720 ? [accountControl] : [],
        maxDiffPixelRatio: 0.005,
      });
      await dialog.getByRole("button", { name: "Abbrechen" }).click();

      await inspector.getByRole("button", { name: "Schließen" }).click();
      await page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await page.goto(phasePropertiesUrl);
      await expect(inspector).toBeVisible();
      await page.evaluate(() => window.scrollTo(0, 0));
      if (viewport.width > 720) {
        await fitVisibleGraph(page);
        await expect(phaseLink).toBeInViewport({ ratio: 0.2 });
        if (viewport.width >= 1200) await expectCenteredGraphContext(page);
      }
      await expect(page).toHaveScreenshot(`teacher-graph-inspector-dark-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: viewport.width > 720 ? [accountControl] : [],
        maxDiffPixelRatio: 0.005,
      });
      await inspector.getByRole("button", { name: "Phase löschen" }).click();
      await expect(page.getByRole("dialog", { name: "Phase löschen" })).toBeVisible();
      await expect(page).toHaveScreenshot(`teacher-graph-delete-dark-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide",
        mask: viewport.width > 720 ? [accountControl] : [],
        maxDiffPixelRatio: 0.005,
      });
      await page.getByRole("dialog", { name: "Phase löschen" }).getByRole("button", { name: "Abbrechen" }).click();
      await inspector.getByRole("button", { name: "Schließen" }).click();
      await page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
      await page.goto(phasePropertiesUrl);
      await expect(inspector).toBeVisible();
    }
  });

  test("@design-system renders the active catalog, school-year archive and personal learning archive", async ({ browser }) => {
    test.setTimeout(180_000);
    const unique = Date.now();
    const teacherEmail = `visual_teacher_archive_${unique}@${emailDomain}`;
    const learnerEmail = `visual_learner_archive_${unique}@${emailDomain}`;
    await ensureTeacherUser(teacherEmail, password);
    await ensureLearnerUser(learnerEmail, password);
    const teacher = await newSmokePage(browser);
    const learner = await newSmokePage(browser);

    const capture = async (page: Page, prefix: string) => {
      await page.evaluate(async () => { await document.fonts.ready; });
      await page.locator("time").evaluateAll((items) => {
        for (const item of items) item.textContent = "01.08.2026, 12:00";
      });
      await page.locator(".learning-portfolio__feedback").evaluateAll((items) => {
        for (const item of items) {
          item.innerHTML = "<p>Die Rückmeldung ordnet die eigene Lernleistung nachvollziehbar ein und nennt einen konkreten nächsten Schritt.</p>";
        }
      });
      for (const viewport of [
        { name: "desktop", width: 1440, height: 900 },
        { name: "tablet", width: 1024, height: 768 },
        { name: "mobile", width: 390, height: 844 },
      ]) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await expectNoViewportOverflow(page);
        const masks = [page.locator(".account-trigger"), page.locator("time")];
        await expect(page).toHaveScreenshot(`${prefix}-light-${viewport.name}.png`, {
          animations: "disabled", caret: "hide", fullPage: true, mask: masks,
        });
        await page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
        await expect(page).toHaveScreenshot(`${prefix}-dark-${viewport.name}.png`, {
          animations: "disabled", caret: "hide", fullPage: true, mask: masks,
        });
        await page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
      }
    };

    try {
      await login(teacher.page, teacherEmail, password);
      await login(learner.page, learnerEmail, password);
      const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, "Visual Kursarchiv");

      await teacher.page.goto("/teaching/courses");
      await expect(teacher.page.getByRole("link", { name: seeded.courseTitle, exact: true })).toBeVisible();
      await teacher.page.setViewportSize({ width: 1440, height: 900 });
      const courseCatalogBox = await teacher.page.locator(".teacher-catalog").evaluate((element) => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right, width: box.width };
      });
      await capture(teacher.page, "teacher-courses-active");

      await teacher.page.goto(`/teaching/courses/${seeded.courseId}`);
      await teacher.page.setViewportSize({ width: 1440, height: 900 });
      await expect(teacher.page.locator(".teacher-course-workspace")).toBeVisible();
      const courseWorkspaceBox = await teacher.page.locator(".teacher-course-workspace").evaluate((element) => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right, width: box.width };
      });
      expect(Math.abs(courseCatalogBox.left - courseWorkspaceBox.left)).toBeLessThanOrEqual(1);
      expect(Math.abs(courseCatalogBox.right - courseWorkspaceBox.right)).toBeLessThanOrEqual(1);
      expect(Math.abs(courseCatalogBox.width - courseWorkspaceBox.width)).toBeLessThanOrEqual(1);
      await capture(teacher.page, "teacher-course-detail-active");

      await makeCourseMetadataIncomplete(seeded.courseId);
      await teacher.page.reload();
      await expect(teacher.page.getByText("Kursdaten unvollständig:")).toBeVisible();
      await capture(teacher.page, "teacher-course-detail-incomplete");

      const restoreMetadataResponse = await teacher.page.request.patch(`${webBase}/api/teaching/courses/${seeded.courseId}`, {
        headers: apiHeaders(`/teaching/courses/${seeded.courseId}`),
        data: {
          subject: "Testfach",
          grade_level: "Jahrgangsübergreifend",
          school_year_start: new Date().getFullYear()
        }
      });
      await expectApiOk(restoreMetadataResponse, 200);

      await teacher.page.goto("/teaching/units");
      await expect(teacher.page.getByRole("link", { name: seeded.unitTitle, exact: true })).toBeVisible();
      await teacher.page.setViewportSize({ width: 1440, height: 900 });
      const unitCatalogBox = await teacher.page.locator(".teacher-catalog").evaluate((element) => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right, width: box.width };
      });
      expect(Math.abs(courseCatalogBox.left - unitCatalogBox.left)).toBeLessThanOrEqual(1);
      expect(Math.abs(courseCatalogBox.right - unitCatalogBox.right)).toBeLessThanOrEqual(1);
      expect(Math.abs(courseCatalogBox.width - unitCatalogBox.width)).toBeLessThanOrEqual(1);
      await capture(teacher.page, "teacher-units-catalog");

      await teacher.page.goto("/teaching/courses");
      const row = teacher.page.locator(".workspace-course-catalog__row").filter({ hasText: seeded.courseTitle });
      await row.getByRole("checkbox").check();
      await teacher.page.getByRole("button", { name: "Archivieren" }).click();
      await teacher.page.goto("/teaching/courses?status=archived");
      await expect(teacher.page.getByRole("link", { name: seeded.courseTitle, exact: true })).toBeVisible();
      await capture(teacher.page, "teacher-courses-archive");

      await teacher.page.goto(`/teaching/courses/${seeded.courseId}`);
      await expect(teacher.page.getByText("Archiviert · schreibgeschützt")).toBeVisible();
      await capture(teacher.page, "teacher-course-detail-archived");

      await learner.page.goto(`/learning/courses/${seeded.courseId}/archive`);
      await expect(learner.page.getByText(seeded.previousSubmissionText)).toBeVisible();
      await capture(learner.page, "learner-course-archive");
    } finally {
      await teacher.context.close();
      await learner.context.close();
    }
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
        const desk = workspace.querySelector(".learner-task-workbench__desk");
        const context = workspace.querySelector('[data-work-surface="materials"]');
        const task = workspace.querySelector('[data-work-surface="task"]');
        if (!(desk instanceof HTMLElement) || !(context instanceof HTMLElement) || !(task instanceof HTMLElement)) {
          throw new Error("learner work surfaces are incomplete");
        }
        return {
          context: context.getBoundingClientRect().toJSON(),
          task: task.getBoundingClientRect().toJSON(),
          columns: getComputedStyle(desk).gridTemplateColumns
        };
      });
      expect(desktopGeometry.columns.split(" ")).toHaveLength(2);
      expect(desktopGeometry.task.x).toBeGreaterThan(
        desktopGeometry.context.x + desktopGeometry.context.width - 1
      );
      await expect(learner.page).toHaveScreenshot("learner-work-light-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
      await expectLearnerTaskTheme(learner.page, "light");

      await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await expectLearnerTaskTheme(learner.page, "dark");
      await expect(learner.page).toHaveScreenshot("learner-work-dark-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
      const sourceSection = contextSurface.getByRole("button", { name: "Modul Vertiefung ein- oder ausklappen" });
      await expect(sourceSection).toBeVisible();
      await sourceSection.click();
      await contextSurface.locator(".learner-task-context__scroll").evaluate((surface) => {
        surface.scrollTop = surface.scrollHeight;
      });
      await expectLearnerMaterialContrast(learner.page);
      await expect(learner.page).toHaveScreenshot("learner-material-list-dark-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
      await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
      await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "light");
      await expectLearnerMaterialContrast(learner.page);
      await expect(learner.page).toHaveScreenshot("learner-material-list-light-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
      await contextSurface.locator(".learner-task-context__scroll").evaluate((surface) => {
        surface.scrollTop = 0;
      });

      const currentMaterial = contextSurface
        .locator(".learner-reference-document")
        .filter({ hasText: "Grundrechte und digitale Kommunikation" });
      await currentMaterial.getByRole("button", { name: "Grundrechte und digitale Kommunikation groß lesen" }).click();
      const reader = workbench.getByRole("region", { name: "Dokument groß lesen" });
      await expect(reader).toBeVisible();
      await expect(reader.getByRole("heading", { name: "Grundrechte und digitale Kommunikation" })).toBeVisible();
      const readingMeasure = await reader.locator(".learner-reference-document__prose").first().evaluate((body) => ({
        width: body.getBoundingClientRect().width,
        maxWidth: Number.parseFloat(getComputedStyle(body).maxWidth)
      }));
      expect(readingMeasure.width).toBeLessThanOrEqual(readingMeasure.maxWidth + 1);
      await expect(learner.page).toHaveScreenshot("learner-context-light-desktop.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
      await reader.getByRole("button", { name: "Zurück zur Aufgabe" }).click();

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
        await contextSurface.locator(".learner-task-context__scroll").evaluate((surface) => {
          surface.scrollTop = surface.scrollHeight;
        });
        await expectLearnerMaterialContrast(learner.page);
        await expect(learner.page).toHaveScreenshot(`learner-material-list-light-${viewport.name}.png`, {
          animations: "disabled",
          caret: "hide",
          mask: [accountControl]
        });
        await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
        await expectLearnerMaterialContrast(learner.page);
        await expect(learner.page).toHaveScreenshot(`learner-material-list-dark-${viewport.name}.png`, {
          animations: "disabled",
          caret: "hide",
          mask: [accountControl]
        });
        await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
        await contextSurface.locator(".learner-task-context__scroll").evaluate((surface) => {
          surface.scrollTop = 0;
        });
      }

      await workbench.getByRole("button", { name: "Aufgabe" }).click();
      await expect(taskSurface).toBeVisible();
      await expect(contextSurface).toBeHidden();
      await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await expectLearnerTaskTheme(learner.page, "dark");
      await expect(learner.page).toHaveScreenshot("learner-work-dark-mobile.png", {
        animations: "disabled",
        caret: "hide",
        mask: [accountControl]
      });
      await workbench.getByRole("button", { name: "Materialien" }).click();
      await expect(contextSurface).toBeVisible();
      await expect(taskSurface).toBeHidden();
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
