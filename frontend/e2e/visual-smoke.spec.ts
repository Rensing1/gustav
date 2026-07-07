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
  test("renders a released learner unit with real membership data", async ({ browser }) => {
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
      const seeded = await seedLearnerVisualSmokeCourse(teacher.page, learner.page, `Visual Smoke ${unique}`);

      await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
      await expect(learner.page.getByRole("heading", { name: seeded.unitTitle })).toBeVisible();
      await expect(learner.page.getByText("Beschreibe in zwei Sätzen", { exact: false })).toBeVisible();
      await expectInteractiveSurface(learner.page.locator(".learning-unit-content-shell"));
      await expectNoViewportOverflow(learner.page);
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
      await expectInteractiveSurface(learner.page.locator(".learning-unit-content-shell"));
      await expectNoViewportOverflow(learner.page);
    } finally {
      await learner.context.close();
      await teacher.context.close();
    }
  });
});
