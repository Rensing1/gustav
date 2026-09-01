import { expect, test } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureLearnerUser } from "./support/keycloak";

const password = e2ePassword;

test("@feature-acceptance student profile does not expose CLI token management", async ({ page }) => {
  const learnerEmail = e2eEmail("learner");
  await ensureLearnerUser(learnerEmail, password);
  await login(page, learnerEmail, password);

  await page.goto("/profile");

  await expect(page.getByRole("heading", { name: "Profil" })).toBeVisible();
  await expect(page.getByText("CLI-Tokens")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "CLI-Token erstellen" })).toHaveCount(0);
});
