import type { Page } from "@playwright/test";
import { test, expect } from "./support/feature-test";
import { ensureLearnerUser } from "./support/keycloak";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { login } from "./support/auth";

async function standardLoginJourney(page: Page) {
  const email = e2eEmail("auth.platform");
  await ensureLearnerUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  await page.goto("/learning");
  await expect(page).toHaveURL(/\/learning/);
  const response = await page.request.get("/api/me");
  expect(response.status()).toBe(200);
  expect((await response.json()).roles).toContain("student");
  let tokenExposed = false;
  page.on('request', request => { if (new URL(request.url()).searchParams.has('id_token_hint')) tokenExposed = true; });
  await page.goto('/auth/logout');
  await page.getByRole('button', { name: 'Abmelden', exact: true }).click();
  await expect(page).toHaveURL(/\/auth\/logout\/success/);
  expect((await page.request.get('/api/me')).status()).toBe(401);
  expect(tokenExposed).toBe(false);
}

async function bcryptLoginJourney(page: Page) {
  const { execFileSync } = await import('node:child_process');
  const { ensureImportedBcryptLearner } = await import('./support/keycloak');
  const hash = execFileSync('../.venv/bin/python', ['-Wignore::DeprecationWarning', '-c', 'import crypt,sys; print(crypt.crypt(sys.stdin.read(), crypt.mksalt(crypt.METHOD_BLOWFISH)))'], { input: e2ePassword }).toString().trim();
  const email = e2eEmail('auth.bcrypt');
  await ensureImportedBcryptLearner(email, hash);
  await login(page, email, e2ePassword);
  await page.goto('/learning');
  await expect(page).toHaveURL(/\/learning/);
  expect((await page.request.get('/api/me')).status()).toBe(200);
}

test("@feature-acceptance Keycloak preserves standard and imported BCrypt logins", async ({ page }) => {
  test.setTimeout(150_000);
  await test.step("Sichere Darstellung eines ungültigen Rücksprungs", async () => {
    await page.goto('/auth/callback?code=invalid');
    await expect(page).toHaveURL(/\/auth\/problem\?reason=invalid_code_or_state$/);
    await expect(page.getByRole('heading', { name: 'Anmeldung prüfen' })).toBeVisible();
    await expect(page.getByText('invalid', { exact: true })).toHaveCount(0);
  });
  await test.step("Normale Anmeldung", () => standardLoginJourney(page));
  await page.context().clearCookies();
  await test.step("Übernommenes BCrypt-Passwort", () => bcryptLoginJourney(page));
});
