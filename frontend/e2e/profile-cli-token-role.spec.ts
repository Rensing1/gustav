import { expect, test } from "./support/feature-test";

import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";

const password = e2ePassword;

test("@feature-acceptance profile self-service preserves role boundaries, name locks and token lifecycle", async ({ browser }) => {
  const learnerContext = await newBrowserContext(browser);
  const teacherContext = await newBrowserContext(browser);
  try {
    const learner = await learnerContext.newPage();
    const teacher = await teacherContext.newPage();
    const learnerEmail = e2eEmail("learner");
    await ensureLearnerUser(learnerEmail, password);
    await login(learner, learnerEmail, password);

    await learner.goto("/profile");

    await expect(learner.getByRole("heading", { name: "Profil" })).toBeVisible();
    await expect(learner.getByText("CLI-Tokens")).toHaveCount(0);
    await expect(learner.getByRole("button", { name: "CLI-Token erstellen" })).toHaveCount(0);

    await learner.getByLabel("Anzeigename", { exact: true }).fill("Profilprüfung");
    await learner.getByRole("button", { name: "Anzeigename speichern", exact: true }).click();
    await expect(learner.getByText("Der Anzeigename wurde gespeichert.", { exact: true })).toBeVisible();
    await learner.reload();
    await expect(learner.getByLabel("Anzeigename", { exact: true })).toHaveValue("Profilprüfung");

    await learner.getByLabel("Vorname", { exact: true }).fill("Profil");
    await learner.getByLabel("Nachname", { exact: true }).fill("Test");
    await learner.getByRole("button", { name: "Vor- und Nachname speichern", exact: true }).click();
    await expect(learner.getByText("Vor- und Nachname wurden gespeichert.", { exact: true })).toBeVisible();
    await learner.reload();
    await expect(learner.getByLabel("Vorname", { exact: true })).toHaveValue("Profil");
    await expect(learner.getByLabel("Nachname", { exact: true })).toHaveValue("Test");
    await expect(learner.getByLabel("Vorname", { exact: true })).toBeDisabled();
    await expect(learner.getByLabel("Nachname", { exact: true })).toBeDisabled();

    const teacherEmail = e2eEmail("profile-teacher");
    await ensureTeacherUser(teacherEmail, password);
    await login(teacher, teacherEmail, password);
    await teacher.goto("/profile");

    await teacher.getByLabel("Tokenname").fill("Profil-Test");
    await teacher.getByRole("button", { name: "CLI-Token erstellen", exact: true }).click();
    // Assert presence only: never copy the one-time secret into logs or fixtures.
    await expect(teacher.locator(".profile-editor__section code")).toBeVisible();
    await teacher.goto("/profile");
    await expect(teacher.locator(".profile-editor__section code")).toHaveCount(0);

    const tokenRow = teacher.locator('form[action="?/revokeCliToken"]').filter({ hasText: "Profil-Test" });
    await expect(tokenRow).toHaveCount(1);
    await tokenRow.getByRole("button", { name: "CLI-Token widerrufen" }).click();
    await expect(teacher.getByText("Das CLI-Token wurde widerrufen.", { exact: true })).toBeVisible();
    await teacher.reload();
    await expect(tokenRow).toContainText("Widerrufen:");
    await expect(tokenRow.getByRole("button", { name: "CLI-Token widerrufen" })).toHaveCount(0);
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
