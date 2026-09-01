import { expect, test } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherHomeWorkStarter } from "./support/seed-data";

test("@feature-acceptance teacher starts live work and resumes authoring from home", async ({ page }) => {
  const unique = Date.now();
  const email = e2eEmail("teacher");
  const password = e2ePassword;
  await ensureTeacherUser(email, password);
  await login(page, email, password);
  const seeded = await seedTeacherHomeWorkStarter(page, `E2E Arbeitsstart ${unique}`);

  await page.goto("/teaching");
  await expect(page.getByRole("heading", { name: "Weiterarbeiten" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Unterrichten" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Vorbereiten" })).toBeVisible();
  await expect(page.getByText("Arbeitsbereiche")).toHaveCount(0);

  const courseSelect = page.getByRole("combobox", { name: "Kurs" });
  const unitSelect = page.getByRole("combobox", { name: "Lerneinheit" });
  const liveButton = page.getByRole("button", { name: "Live öffnen" });
  await expect(courseSelect).toHaveValue("");
  await expect(unitSelect).toBeDisabled();
  await expect(liveButton).toBeDisabled();

  await courseSelect.selectOption(seeded.courseId);
  await expect(unitSelect).toBeEnabled();
  await unitSelect.selectOption(seeded.unitId);
  await expect(liveButton).toBeEnabled();
  await liveButton.click();
  await expect(page).toHaveURL(new RegExp(`/live\\?course_id=${seeded.courseId}&unit_id=${seeded.unitId}$`));

  await page.goto("/teaching");
  await page.getByRole("link", { name: new RegExp(seeded.unitTitle) }).click();
  await expect(page).toHaveURL(`/teaching/units/${seeded.unitId}`);

  await page.goto("/teaching");
  await page.getByRole("link", { name: "Neue Lerneinheit" }).click();
  await expect(page).toHaveURL(/\/teaching\/units\?create=1$/);
  await expect(page.getByRole("dialog", { name: "Neue Lerneinheit" })).toBeVisible();
});
