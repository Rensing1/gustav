import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

test("@feature-acceptance learner course overview preserves navigation and archived course links", async ({ browser }) => {
  test.setTimeout(90_000);
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    await learner.goto("/learning");
    await expect(learner.getByText("Noch keine Klassen sichtbar.")).toBeVisible();
    const seeded = await seedLearnerNavigationCourse(teacher, learner, `Kursübersicht ${Date.now()}`);

    await learner.reload();
    const courseLink = learner.getByRole("link", { name: seeded.courseTitle });
    await expect(courseLink).toHaveAttribute("href", `/learning/courses/${seeded.courseId}`);
    await courseLink.click();
    const unitLink = learner.getByRole("link", { name: seeded.unitTitle, exact: true });
    await expect(unitLink).toBeVisible();
    await unitLink.click();
    await expect(learner).toHaveURL(new RegExp(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}$`));
    // The standalone course API is also used by non-browser clients.
    const current = await learner.request.get("/api/learning/courses");
    expect(current.status()).toBe(200);
    expect((await current.json()).map((course: { id: string }) => course.id)).toEqual([seeded.courseId]);

    await teacher.goto("/teaching/courses");
    const row = teacher.locator(".workspace-course-catalog__row").filter({ hasText: seeded.courseTitle });
    await row.getByRole("checkbox").check();
    await teacher.getByRole("button", { name: "Archivieren", exact: true }).click();
    await expect(teacher).toHaveURL(/\/teaching\/courses\?status=archived$/);
    await expect(row).toBeVisible();

    await learner.goto("/learning");
    await learner.reload();
    await expect(learner.getByText("Noch keine Klassen sichtbar.")).toBeVisible();
    await expect(learner.getByRole("heading", { name: "Vergangene Kurse" })).toBeVisible();
    await expect(courseLink).toHaveAttribute("href", `/learning/courses/${seeded.courseId}/archive`);
    const past = await learner.request.get("/api/learning/courses?scope=past");
    expect(past.status()).toBe(200);
    expect((await past.json()).map((course: { id: string }) => course.id)).toEqual([seeded.courseId]);
    expect(await (await learner.request.get("/api/learning/courses")).json()).toEqual([]);
    await courseLink.click();
    await expect(learner).toHaveURL(new RegExp(`/learning/courses/${seeded.courseId}/archive$`));
    await expect(learner.locator(".learning-portfolio")).toBeVisible();
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
