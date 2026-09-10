import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

test("@feature-acceptance teacher opens the ordered live task summary and retains selection", async ({ browser }) => {
  test.setTimeout(120_000);
  const teacherEmail = e2eEmail("live-teacher");
  const learnerEmail = e2eEmail("live-learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  teacherContext.setDefaultTimeout(15_000);
  learnerContext.setDefaultTimeout(15_000);
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, "Live-Reihenfolge");

    await teacher.getByRole("link", { name: "Live", exact: true }).click();
    await teacher.getByRole("combobox", { name: "Kurs", exact: true }).selectOption(seeded.courseId);
    await teacher.getByRole("combobox", { name: "Lerneinheit", exact: true }).selectOption(seeded.unitId);
    await expect(teacher.getByRole("heading", { name: "Lernstand in der gewählten Lerneinheit" })).toBeVisible();
    await expect(teacher.locator(".workspace-data-table tbody tr")).toHaveCount(1);
    await teacher.locator(".workspace-data-table tbody tr td a").first().click();

    const taskLinks = teacher.getByRole("navigation", { name: "Aufgaben der Lerneinheit" }).getByRole("link");
    await expect(taskLinks).toHaveCount(3);
    await expect(teacher.getByRole("region", { name: "Grundlagen", exact: true })).toContainText("Aufgabe 1");
    await expect(teacher.getByRole("region", { name: "Grundlagen", exact: true })).toContainText("Aufgabe 2");
    await expect(teacher.getByRole("region", { name: "Quellen", exact: true })).toContainText("Aufgabe 1");
    for (const [index, id] of [seeded.taskId, seeded.secondTaskId, seeded.contextTaskId].entries()) {
      await expect(taskLinks.nth(index)).toHaveAttribute("href", new RegExp(`task_id=${id}`));
    }
    await taskLinks.nth(2).click();
    await expect(teacher).toHaveURL(new RegExp(`task_id=${seeded.contextTaskId}`));
    await teacher.reload();
    await expect(taskLinks.nth(2)).toHaveClass(/is-active/);
    await expect(teacher.getByRole("complementary", { name: "Schülerdetail" })).toContainText("Keine Abgabe");

    const forbidden = await learner.request.get(
      `/api/teaching/courses/${seeded.courseId}/units/${seeded.unitId}/submissions/summary`
    );
    expect(forbidden.status()).toBe(403);
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
