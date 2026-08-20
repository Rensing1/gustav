import { expect, test } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureLearnerUser } from "./support/keycloak";

const password = "Passw0rd!e2e";

test("@feature-acceptance student profile does not expose CLI token management", async ({ page }) => {
  const learnerEmail = `e2e_learner_profile_cli_${Date.now()}@${emailDomain}`;
  await ensureLearnerUser(learnerEmail, password);
  await login(page, learnerEmail, password);

  await page.goto("/profile");

  await expect(page.getByRole("heading", { name: "Profil" })).toBeVisible();
  await expect(page.getByText("CLI-Tokens")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "CLI-Token erstellen" })).toHaveCount(0);
});
