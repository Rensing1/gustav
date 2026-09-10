import { newBrowserContext } from "./support/browser-context";
import { expect, test } from "./support/feature-test";
import { authPictures } from "./support/auth-design";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, emailDomain, kcBase, realm, webBase } from "./support/e2e-env";
import { ensureLearnerUser, useTemporaryRealmSmtp } from "./support/keycloak";
import { startSmtpCapture } from "./support/smtp-capture";

test("@feature-acceptance email login reset logout and consumed mail links share a safe readable theme", async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const email = e2eEmail("auth-design");
  await ensureLearnerUser(email, e2ePassword);
  const context = await newBrowserContext(browser, { locale: "de-DE" });
  const mailContext = await newBrowserContext(browser, { locale: "de-DE", colorScheme: "dark" });
  const smtp = await startSmtpCapture();
  const restoreSmtp = await useTemporaryRealmSmtp({ host: smtp.host, port: String(smtp.port), from: `noreply@${emailDomain}`, auth: "false", starttls: "false", ssl: "false" });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
    await page.getByRole("link", { name: "Anmelden", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${kcBase}/realms/${realm}/protocol/openid-connect/auth`));
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const address = page.getByRole("textbox", { name: "E-Mail-Adresse", exact: true });
    await expect(address).toHaveAttribute("type", "email");
    await expect(address).toHaveAttribute("autocomplete", "email");
    await address.fill("kein-konto-name");
    await page.getByRole("button", { name: "Anmelden", exact: true }).click();
    await expect.poll(() => address.evaluate((node) => (node as HTMLInputElement).validity.typeMismatch)).toBe(true);
    await address.fill("");
    await authPictures(page, testInfo, "login");

    // Only the two public display values are accepted; no query value becomes markup.
    const invalidHint = new URL(page.url());
    invalidHint.searchParams.set("gustav_theme", "unbekannt");
    await page.goto(invalidHint.toString());
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByRole("link", { name: /Passwort vergessen/ }).click();
    await expect(page.getByRole("textbox", { name: "E-Mail-Adresse", exact: true })).toHaveAttribute("autocomplete", "email");
    await authPictures(page, testInfo, "reset-request");
    await page.getByRole("textbox", { name: "E-Mail-Adresse", exact: true }).fill(email);
    await page.locator(".kc-submit").click();
    const resetUrl = await smtp.verificationUrl(email);

    const mail = await mailContext.newPage();
    await mail.goto(resetUrl);
    await expect(mail.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(mail.locator('[name="password-new"]')).toBeVisible();
    await authPictures(mail, testInfo, "reset-password");
    const replacementPassword = `${e2ePassword}Reset1!`;
    await mail.locator('[name="password-new"]').fill(replacementPassword);
    await mail.locator('[name="password-confirm"]').fill(`${replacementPassword}Mismatch`);
    await mail.locator(".kc-submit").click();
    await expect(mail.locator(".kc-message")).toBeVisible();
    await mail.locator('[name="password-new"]').fill(replacementPassword);
    await mail.locator('[name="password-confirm"]').fill(replacementPassword);
    await mail.locator(".kc-submit").click();
    await expect(mail.locator('[name="password-new"]')).toHaveCount(0);

    await login(page, email, replacementPassword);
    expect((await page.request.get(`${webBase}/api/me`)).status()).toBe(200);
    await page.goto("/auth/logout");
    await expect.poll(async () => (await page.request.get(`${webBase}/api/me`)).status()).toBe(401);

    await mail.goto(resetUrl);
    await expect(mail.locator('[name="password-new"]')).toHaveCount(0);
    await authPictures(mail, testInfo, "consumed-link");
    const recovery = mail.getByRole("link", { name: "Erneut anmelden", exact: true });
    await expect(recovery).toHaveAttribute("href", `${webBase}/auth/login`);
    await recovery.click();
    await expect(mail.locator("#kc-form-login")).toBeVisible();

    const invalidToken = await mail.goto(`${kcBase}/realms/${realm}/login-actions/action-token?key=invalid&pageRedirectUri=https://untrusted.example/`);
    expect(invalidToken?.status()).toBe(400);
    await expect(mail.getByRole("link", { name: "Erneut anmelden", exact: true })).toHaveAttribute("href", `${webBase}/auth/login`);
    await expect(mail.locator('a[href^="https://untrusted.example"]')).toHaveCount(0);
  } finally {
    await Promise.allSettled([context.close(), mailContext.close()]);
    try { await restoreSmtp(); } finally { await smtp.close(); }
  }
});
