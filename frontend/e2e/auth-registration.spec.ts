import type { Browser } from "@playwright/test";
import { test, expect } from "./support/feature-test";
import { newBrowserContext } from './support/browser-context';
import { e2eEmail, e2ePassword, emailDomain } from './support/e2e-env';
import { registerE2EUser } from './support/e2e-run-state';
import { useTemporaryRealmSmtp } from './support/keycloak';
import { startSmtpCapture } from './support/smtp-capture';

// JavaScript is disabled deliberately: Keycloak owns all password/domain rules.
async function registrationJourney(browser: Browser) {
  test.setTimeout(90_000);
  const email = e2eEmail('auth.registration');
  registerE2EUser({ email, role: 'student' });
  const smtp = await startSmtpCapture();
  const restore = await useTemporaryRealmSmtp({ host: smtp.host, port: String(smtp.port), from: `noreply@${emailDomain}`, auth: 'false', ssl: 'false', starttls: 'false' });
  const context = await newBrowserContext(browser, { javaScriptEnabled: false, locale: 'de-DE' });
  try {
    const page = await context.newPage();
    await page.goto('/register');
    await expect(page.locator('#kc-register-form')).toBeVisible();
    await expect(page.locator('#password-requirements li')).toHaveCount(5);
    await page.locator('#display_name').fill('Test Schüler');
    await page.locator('#email').fill('student@invalid.example');
    await page.locator('#password').fill('x');
    await page.locator('#password-confirm').fill('x');
    await page.locator('button[type=submit]').click();
    await expect(page.locator('.kc-message')).toBeVisible();
    await expect(page.locator('#display_name')).toHaveValue('Test Schüler');
    await expect(page.locator('#email')).toHaveValue('student@invalid.example');
    await expect(page.locator('#email')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('#email-error')).toBeVisible();
    await expect(page.locator('#password')).toHaveValue('');
    await expect(page.locator('#password-requirements li')).toHaveCount(5);
    await page.locator('#email').fill(email);
    await page.locator('#password').fill(e2ePassword);
    await page.locator('#password-confirm').fill(e2ePassword);
    await page.locator('button[type=submit]').click();
    await expect(page.getByRole('heading', { name: /E-Mail.*bestätigen|E-Mail.*verifizieren/i })).toBeVisible();
    await page.goto(await smtp.verificationUrl(email));
    const back = page.getByRole('link', { name: /Zurück zur Anwendung|Back to Application|Weiter zu GUSTAV/i });
    if (await back.isVisible()) await back.click();
    await expect.poll(async () => (await page.request.get('/api/me')).status()).toBe(200);
    await page.goto('/learning');
    await expect(page).toHaveURL(/\/learning/);
  } finally {
    await context.close();
    try { await restore(); } finally { await smtp.close(); }
  }
}

async function passwordJourney(browser: Browser) {
  const { ensureLearnerUser } = await import('./support/keycloak');
  const email = e2eEmail('auth.password-reset');
  await ensureLearnerUser(email, e2ePassword);
  const smtp = await startSmtpCapture();
  const restore = await useTemporaryRealmSmtp({ host: smtp.host, port: String(smtp.port), from: `noreply@${emailDomain}`, auth: 'false', ssl: 'false', starttls: 'false' });
  const context = await newBrowserContext(browser, { locale: 'de-DE', javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto('/');
    await page.getByRole('link', { name: 'Passwort vergessen', exact: true }).click();
    await expect(page).toHaveURL(/\/forgot-password/);
    await page.getByRole('button', { name: 'Passwort vergessen', exact: true }).click();
    await expect(page.locator('input[name=username]')).toBeVisible();
    await page.locator('input[name=username]').fill(email);
    await page.locator('button[type=submit]').click();
    await page.goto(await smtp.verificationUrl(email));
    await expect(page.locator('#password-requirements li')).toHaveCount(5);
    await page.locator('#password-new').fill('x');
    await page.locator('#password-confirm').fill('x');
    await page.locator('button[type=submit]').click();
    await expect(page.locator('#password-new')).toHaveValue('');
    await expect(page.locator('#password-new')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('#password-requirements li')).toHaveCount(5);
    await page.locator('#password-new').fill(e2ePassword);
    await page.locator('#password-confirm').fill(e2ePassword);
    await page.locator('button[type=submit]').click();
    const back = page.getByRole('link', { name: /Zurück zur Anwendung|Back to Application|Weiter zu GUSTAV/i });
    if (await back.isVisible()) await back.click();
    await expect.poll(async () => (await page.request.get('/api/me')).status()).toBe(200);
    await page.goto('/auth/password');
    await expect(page.locator('#password-requirements li')).toHaveCount(5);
    await page.locator('#password-new').fill(e2ePassword);
    await page.locator('#password-confirm').fill(e2ePassword);
    await page.locator('button[type=submit]').click();
    await expect(page).toHaveURL(/\/profile/);
    expect((await page.request.get('/api/me')).status()).toBe(200);
  } finally {
    await context.close();
    try { await restore(); } finally { await smtp.close(); }
  }
}

test("@feature-acceptance registration, verification and password recovery retain the active policy", async ({ browser }) => {
  test.setTimeout(150_000);
  await test.step("Registrieren und E-Mail bestätigen", () => registrationJourney(browser));
  await test.step("Passwort zurücksetzen und ändern", () => passwordJourney(browser));
});
