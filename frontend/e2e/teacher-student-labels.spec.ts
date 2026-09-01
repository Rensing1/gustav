import { expect, test } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureLearnerUserProfile, ensureTeacherUser } from "./support/keycloak";
import { seedTeacherStudentLabelCourse } from "./support/seed-data";

const password = e2ePassword;

test("@feature-acceptance teacher surfaces use one learner label and hide diagnostics navigation", async ({ page }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const namedEmail = e2eEmail("named.learner");
  const fallbackEmail = e2eEmail("fallback.mixed-10");
  const fallbackLocalpart = fallbackEmail.split("@", 1)[0];

  await ensureTeacherUser(teacherEmail, password);
  const namedSub = await ensureLearnerUserProfile(namedEmail, password, {
    firstName: "Nora",
    lastName: "Namensgleich",
    displayName: "Nicht anzeigen"
  });
  const fallbackSub = await ensureLearnerUserProfile(fallbackEmail, password, {
    firstName: "Nurvorname",
    lastName: "",
    displayName: "Ebenfalls nicht anzeigen"
  });

  await login(page, teacherEmail, password);
  const seeded = await seedTeacherStudentLabelCourse(
    page,
    [namedSub, fallbackSub],
    `E2E Namensvertrag ${unique}`
  );

  await page.goto(`/teaching/courses/${seeded.courseId}`);
  const primaryNavigation = page.getByRole("navigation", { name: "Hauptnavigation" });
  await expect(primaryNavigation.getByRole("link", { name: "Kurse" })).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: "Lerneinheiten" })).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: "Live" })).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: "Diagnostik" })).toHaveCount(0);

  await page.getByRole("button", { name: "Mitglieder verwalten" }).click();
  const members = page.getByRole("dialog", { name: "Mitglieder verwalten" });
  await expect(members.getByText("Nora Namensgleich", { exact: true })).toBeVisible();
  await expect(members.getByText(fallbackLocalpart, { exact: true })).toBeVisible();
  await expect(members.getByText("Nicht anzeigen", { exact: true })).toHaveCount(0);
  await members.getByRole("button", { name: "Schließen" }).click();

  await page.goto(`/live?course_id=${seeded.courseId}&unit_id=${seeded.unitId}`);
  await expect(page.getByText("Nora Namensgleich", { exact: true })).toBeVisible();
  await expect(page.getByText(fallbackLocalpart, { exact: true })).toBeVisible();

  await page.goto(`/diagnostics/courses/${seeded.courseId}`);
  await expect(page.getByText("Nora Namensgleich", { exact: true })).toBeVisible();
  await expect(page.getByText(fallbackLocalpart, { exact: true })).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: "Diagnostik" })).toHaveCount(0);
});
