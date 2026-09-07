import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

test("@feature-acceptance preserves anonymous and named concerns through archive and restore", async ({ browser }) => {
  test.setTimeout(90_000);
  const teacherEmail = e2eEmail("concern-teacher");
  const learnerEmail = e2eEmail("concern-learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser, { baseURL: webBase });
  const learnerContext = await newBrowserContext(browser, { baseURL: webBase });
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const teacherUser = await (await teacher.request.get("/api/me")).json();
    const learnerUser = await (await learner.request.get("/api/me")).json();
    expect(teacherUser.roles).toContain("teacher");
    expect(learnerUser.roles).toContain("student");
    expect(learnerUser.roles).not.toContain("teacher");
    expect(learnerUser.sub === teacherUser.sub).toBe(false);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, `Kummerkasten ${Date.now()}`);
    const anonymousMessage = "Bitte mehr Zeit für die nächste Übung einplanen.";
    const namedMessage = "Ich möchte die nächste Lösung vorstellen.";
    await learner.goto("/learning/kummerkasten");
    await expect(learner).toHaveURL(/\/learning\/kummerkasten$/);
    for (const [message, anonymous] of [[anonymousMessage, true], [namedMessage, false]] as const) {
      await learner.getByRole("combobox", { name: /Kurs/ }).selectOption(seeded.courseId);
      await learner.getByLabel("Beitrag", { exact: true }).fill(message);
      await learner.getByLabel("Anonym bleiben").setChecked(anonymous);
      await learner.getByRole("button", { name: "Beitrag senden" }).click();
      await expect(learner.getByText("Dein Beitrag wurde gesendet.")).toBeVisible();
      // Wait for the redirect and reset before composing another contribution.
      await expect(learner.getByLabel("Beitrag", { exact: true })).toHaveValue("");
    }

    await teacher.goto("/teaching/kummerkasten");
    const anonymousEntry = teacher.locator("article.concern-box-entry").filter({ hasText: anonymousMessage });
    const namedEntry = teacher.locator("article.concern-box-entry").filter({ hasText: namedMessage });
    await expect(anonymousEntry.locator(".workspace-note")).toHaveText("Anonym");
    await expect(namedEntry.locator(".workspace-note")).not.toHaveText(/^(Anonym|Unbekannt)$/);
    await anonymousEntry.getByRole("button", { name: "Archivieren", exact: true }).click();
    await expect(anonymousEntry).toHaveCount(0);
    await expect(namedEntry).toBeVisible();

    await teacher.getByRole("link", { name: "Archiv", exact: true }).click();
    await expect(teacher).toHaveURL(/scope=archived$/);
    await expect(anonymousEntry).toBeVisible();
    await teacher.reload();
    await expect(anonymousEntry.locator(".workspace-note")).toHaveText("Anonym");
    await expect(namedEntry).toHaveCount(0);
    await anonymousEntry.getByRole("button", { name: "Wiederherstellen" }).click();
    await expect(anonymousEntry).toHaveCount(0);
    await teacher.getByRole("link", { name: "Offen", exact: true }).click();
    await expect(teacher).toHaveURL(/scope=open$/);
    await expect(anonymousEntry).toBeVisible();
    await teacher.reload();
    await expect(anonymousEntry).toBeVisible();
    await expect(namedEntry).toBeVisible();
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
