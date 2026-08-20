import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, hasTouch: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance keeps the learner task desk split on landscape iPads", async ({ browser }) => {
  const unique = Date.now();
  const teacherEmail = `responsive_task_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `responsive_task_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Responsive Aufgabe ${unique}`);

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    const taskRow = learner.page.locator(".learning-task-row").first();
    await expect(taskRow.getByText("Weitere Angaben in der Aufgabe")).toBeVisible();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();

    const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const context = workbench.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const task = workbench.getByRole("main", { name: "Bearbeitung" });
    const switcher = workbench.getByRole("navigation", { name: "Arbeitsbereich wählen" });
    const compactStatement = workbench.getByRole("region", { name: "Vollständige Aufgabenstellung" });

    await expect(context).toBeVisible();
    await expect(task).toBeVisible();
    await expect(switcher).toBeHidden();
    await expect(compactStatement).toBeHidden();
    await expect(context.getByText("Begründe abschließend, welche Position dich überzeugt.")).toBeVisible();
    const landscapeColumns = await workbench.locator(".learner-task-workbench__desk").evaluate(
      (desk) => getComputedStyle(desk).gridTemplateColumns.split(" ").length
    );
    expect(landscapeColumns).toBe(2);
    await expectNoViewportOverflow(learner.page);

    await learner.page.addStyleTag({
      content: `
        .learner-task-context__scroll::after,
        .learner-task-workbench__main::after {
          content: "";
          display: block;
          height: 80rem;
        }
      `
    });
    const contextScroll = workbench.locator(".learner-task-context__scroll");
    const workScroll = workbench.locator(".learner-task-workbench__main");
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight)).toBeGreaterThan(500);
    await expect.poll(() => workScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight)).toBeGreaterThan(500);

    await contextScroll.evaluate((surface) => {
      surface.scrollTop = surface.scrollHeight;
      surface.dispatchEvent(new Event("scroll"));
    });
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight - surface.scrollTop)).toBeLessThan(2);
    expect(await workScroll.evaluate((surface) => surface.scrollTop)).toBe(0);

    const contextBottom = await contextScroll.evaluate((surface) => surface.scrollTop);
    await workScroll.evaluate((surface) => {
      surface.scrollTop = surface.scrollHeight;
      surface.dispatchEvent(new Event("scroll"));
    });
    await expect.poll(() => workScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight - surface.scrollTop)).toBeLessThan(2);
    expect(await contextScroll.evaluate((surface) => surface.scrollTop)).toBe(contextBottom);

    await contextScroll.evaluate((surface) => {
      surface.scrollTop = 0;
      surface.dispatchEvent(new Event("scroll"));
    });
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollTop)).toBe(0);

    await learner.page.setViewportSize({ width: 1180, height: 820 });
    await expect(context).toBeVisible();
    await expect(task).toBeVisible();
    await expect(switcher).toBeHidden();
    const largeLandscapeColumns = await workbench.locator(".learner-task-workbench__desk").evaluate(
      (desk) => getComputedStyle(desk).gridTemplateColumns.split(" ").length
    );
    expect(largeLandscapeColumns).toBe(2);
    await expectNoViewportOverflow(learner.page);

    await learner.page.setViewportSize({ width: 820, height: 1180 });
    await expect(context).toBeHidden();
    await expect(task).toBeVisible();
    await expect(switcher).toBeVisible();
    await expect(compactStatement).toBeVisible();
    await expect(compactStatement.getByText("Begründe abschließend, welche Position dich überzeugt.")).toBeVisible();
    const portraitColumns = await workbench.locator(".learner-task-workbench__desk").evaluate(
      (desk) => getComputedStyle(desk).gridTemplateColumns.split(" ").length
    );
    expect(portraitColumns).toBe(1);
    await expectNoViewportOverflow(learner.page);

    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expect(compactStatement).toBeVisible();
    await expect(compactStatement.getByText("Begründe abschließend, welche Position dich überzeugt.")).toBeVisible();
    await expectNoViewportOverflow(learner.page);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
