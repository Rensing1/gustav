import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = e2ePassword;

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase });
  return { context, page: await context.newPage() };
}

async function expectCompatibleStylesheets(page: Page): Promise<void> {
  const stylesheetUrls = await page.locator('link[rel="stylesheet"]').evaluateAll((links) =>
    links.map((link) => (link as HTMLLinkElement).href)
  );
  expect(stylesheetUrls.length).toBeGreaterThan(0);

  for (const stylesheetUrl of stylesheetUrls) {
    const response = await page.request.get(stylesheetUrl);
    expect(response.ok(), `Stylesheet could not be loaded: ${stylesheetUrl}`).toBe(true);
    expect(await response.text(), `Cascade layer remained in: ${stylesheetUrl}`).not.toMatch(
      /@layer(?:\s|\{|;)/i
    );
  }
}

test("@feature-acceptance delivers the authenticated learning view without cascade layers", async ({ browser }) => {
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
    const seeded = await seedLearnerNavigationCourse(
      teacher.page,
      learner.page,
      `iPad-CSS-Kompatibilität ${unique}`
    );

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.locator(".workspace-page")).toBeVisible();

    await expectCompatibleStylesheets(learner.page);
    const layout = await learner.page.evaluate(() => ({
      shellDisplay: getComputedStyle(document.querySelector(".app-shell")!).display,
      topbarPosition: getComputedStyle(document.querySelector(".app-topbar")!).position,
      workspaceDisplay: getComputedStyle(document.querySelector(".workspace-page")!).display
    }));
    expect(layout).toEqual({
      shellDisplay: "block",
      topbarPosition: "sticky",
      workspaceDisplay: "grid"
    });
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
