import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance keeps the concern box one click away for learners and teachers", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `concern_nav_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `concern_nav_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(
      teacher.page,
      learner.page,
      `Kummerkasten-Navigation ${unique}`
    );

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    const learnerConcernLink = learner.page
      .locator(".app-topbar-controls")
      .getByRole("link", { name: "Kummerkasten" });
    await expect(learner.page.locator(".app-topbar-breadcrumbs")).toBeVisible();
    await expect(learnerConcernLink).toBeVisible();
    await expect(learnerConcernLink).toHaveAttribute("href", "/learning/kummerkasten");

    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expect(learnerConcernLink).toBeVisible();
    await expect(learner.page.getByRole("button", { name: /Mode aktivieren/ })).toBeVisible();
    await expect(learner.page.getByLabel("Konto-Menü")).toBeVisible();
    await expectNoViewportOverflow(learner.page);

    await learnerConcernLink.click();
    await expect(learner.page).toHaveURL(/\/learning\/kummerkasten$/);
    await expect(learnerConcernLink).toHaveAttribute("aria-current", "page");
    await learner.page.getByLabel("Konto-Menü").click();
    const learnerAccountMenu = learner.page.locator(".account-menu__panel");
    await expect(learnerAccountMenu.getByRole("link", { name: "Profil" })).toBeVisible();
    await expect(learnerAccountMenu.getByRole("link", { name: "Abmelden" })).toBeVisible();
    await expect(learnerAccountMenu.getByRole("link", { name: "Kummerkasten" })).toHaveCount(0);

    await teacher.page.goto(`/teaching/courses/${seeded.courseId}`);
    const teacherConcernLink = teacher.page
      .locator(".app-topbar-controls")
      .getByRole("link", { name: "Kummerkasten" });
    await expect(teacherConcernLink).toBeVisible();
    await expect(teacherConcernLink).toHaveAttribute("href", "/teaching/kummerkasten");
    await teacherConcernLink.click();
    await expect(teacher.page).toHaveURL(/\/teaching\/kummerkasten$/);
    await expect(teacherConcernLink).toHaveAttribute("aria-current", "page");
    await teacher.page.getByLabel("Konto-Menü").click();
    await expect(
      teacher.page.locator(".account-menu__panel").getByRole("link", { name: "Kummerkasten" })
    ).toHaveCount(0);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
