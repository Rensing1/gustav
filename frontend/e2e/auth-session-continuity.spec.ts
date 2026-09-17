import type { Browser, Page } from "@playwright/test";
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { test, expect } from "./support/feature-test";
import { sessionFixture } from './support/auth-session-fixture';
import { newBrowserContext } from './support/browser-context';
import { ensureLearnerUser } from './support/keycloak';
import { e2eEmail, e2ePassword, kcBase, realm } from './support/e2e-env';

async function rememberJourney(browser: Browser) {
  test.setTimeout(120_000);
  const email = e2eEmail('auth.remember');
  await ensureLearnerUser(email, e2ePassword);
  const context = await newBrowserContext(browser);
  const page = await context.newPage();
  await page.goto('/auth/login');
  await page.locator('input[name=username]').fill(email);
  await page.locator('input[name=password]').fill(e2ePassword);
  await page.locator('input[name=rememberMe]').check();
  await page.locator('button[type=submit]').click();
  await expect.poll(async () => (await page.request.get('/api/me')).status()).toBe(200);
  const all = await context.cookies();
  const session = all.find(cookie => cookie.name === 'gustav_session');
  expect(session).toMatchObject({ secure: true, httpOnly: true, sameSite: 'Lax', expires: -1 });
  expect(all.some(cookie => cookie.name === 'gustav_bff_session')).toBe(false);
  const persistent = all.filter(cookie => cookie.expires > Date.now() / 1000);
  expect(persistent.some(cookie => cookie.name === 'gustav_session')).toBe(false);
  await context.close();
  // The acceptance preflight permits only this local stack. Both services keep their databases.
  execFileSync('docker', ['restart', 'gustav-alpha2', 'gustav-keycloak'], { stdio: 'pipe', timeout: 60_000 });
  const restarted = await chromium.launch();
  try {
    const next = await newBrowserContext(restarted);
    await expect.poll(async () => {
      try { return (await next.request.get(`${kcBase}/realms/${realm}/.well-known/openid-configuration`)).status(); }
      catch { return 0; }
    }, { timeout: 60_000 }).toBe(200);
    await expect.poll(async () => {
      try { return (await next.request.get('/api/me')).status(); }
      catch { return 0; }
    }, { timeout: 60_000 }).toBe(401);
    await next.addCookies(persistent);
    const home = await next.newPage();
    await home.goto('/');
    await expect(home).toHaveURL(/\/learning/, { timeout: 30_000 });
    expect((await home.request.get('/api/me')).status()).toBe(200);
    await home.goto('/auth/logout');
    expect((await home.request.get('/api/me')).status()).toBe(200);
    const identity = await (await home.request.get('/api/me')).json() as { sub: string };
    const sharedCookie = (await next.cookies()).find(cookie => cookie.name === 'gustav_session')!.value;
    expect(sessionFixture('expire-access', sharedCookie, identity.sub)).toBe(true);
    // Pause only while the refresh is in flight; always release the local IdP.
    execFileSync('docker', ['pause', 'gustav-keycloak'], { stdio: 'pipe' });
    const refreshing = home.request.get('/api/me').catch(() => null);
    try {
      await expect.poll(() => sessionFixture('refresh-reserved', sharedCookie, identity.sub), { timeout: 3_000 }).toBe(true);
      const locallyRevoked = home.waitForResponse(response => new URL(response.url()).pathname === '/auth/logout' && response.request().method() === 'POST');
      await home.getByRole('button', { name: 'Abmelden', exact: true }).click({ noWaitAfter: true });
      expect((await locallyRevoked).status()).toBe(302);
    } finally {
      execFileSync('docker', ['unpause', 'gustav-keycloak'], { stdio: 'pipe' });
    }
    expect((await refreshing)?.status()).toBe(401);
    await expect(home).toHaveURL(/\/auth\/problem\?reason=local_logout_only/);
    await expect(home.getByText('Die Abmeldung beim Anmeldedienst konnte noch nicht bestätigt werden.', { exact: false })).toBeVisible();
    expect((await home.request.get('/api/me')).status()).toBe(401);
    await home.getByRole('link', { name: 'Abmeldung erneut versuchen' }).click();
    await home.getByRole('button', { name: 'Abmelden', exact: true }).click();
    // With no remaining app session/token, the IdP confirms logout itself.
    await home.locator('#kc-logout-confirm button[type=submit]').click();
    await expect(home).toHaveURL(/\/auth\/logout\/success/);
    expect((await home.request.get('/api/me')).status()).toBe(401);
    await home.goto('/');
    await expect(home.getByRole('heading', { name: 'Anmelden', exact: true })).toBeVisible();
    expect((await home.request.get('/api/me')).status()).toBe(401);
  } finally { await restarted.close(); }
}

async function neutralJourney(page: Page) {
  let attempts = 0;
  page.on('request', request => { if (request.url().includes('prompt=none')) attempts++; });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Anmelden', exact: true })).toBeVisible();
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Anmelden', exact: true })).toBeVisible();
  expect(attempts).toBe(1);
  await expect(page.getByText('Sitzung abgelaufen.', { exact: false })).toHaveCount(0);
}

test("@feature-acceptance shared sessions survive service and browser restarts with bounded recovery", async ({ browser }) => {
  test.setTimeout(150_000);
  await test.step("Remember-me nach Neustarts und Abmeldung", () => rememberJourney(browser));
  const context = await newBrowserContext(browser);
  try { await test.step("Neutraler Einstieg ohne SSO", async () => neutralJourney(await context.newPage())); }
  finally { await context.close(); }
  await test.step("Abmeldung vor verspäteter Callback-Antwort", () => lateCallbackJourney(browser));
});

async function lateCallbackJourney(browser: Browser) {
  const { login } = await import('./support/auth');
  const email = e2eEmail('auth.late-callback');
  await ensureLearnerUser(email, e2ePassword);
  const context = await newBrowserContext(browser);
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  try {
    const main = await context.newPage();
    await login(main, email, e2ePassword);
    const oldCookie = (await context.cookies()).find(cookie => cookie.name === 'gustav_session')!;
    const late = await context.newPage();
    let captured!: () => void;
    const ready = new Promise<void>(resolve => { captured = resolve; });
    await late.route('**/auth/login', async route => {
      // Playwright intercepts only the first URL of a redirect chain. Follow
      // the real SSO redirects manually so we can hold the callback response.
      const start = await route.fetch({ maxRedirects: 0 });
      const authorization = await context.request.get(start.headers().location, { maxRedirects: 0 });
      expect(new URL(authorization.headers().location).pathname).toBe('/auth/callback');
      const response = await context.request.get(authorization.headers().location, { maxRedirects: 0 });
      expect(response.status()).toBe(302);
      // route.fetch may update the shared cookie jar. Model the actual browser
      // retaining its old cookie until the held response is delivered.
      await context.addCookies([oldCookie]);
      captured();
      await held;
      await route.fulfill({ response });
    });
    const navigation = late.goto('/auth/login');
    await ready;
    await main.goto('/auth/logout');
    await main.getByRole('button', { name: 'Abmelden', exact: true }).click();
    release();
    await navigation;
    await expect.poll(async () => (await main.request.get('/api/me')).status()).toBe(401);
    // Finish the real IdP logout, including its confirmation when required.
    const confirmation = main.locator('#kc-logout-confirm button[type=submit]');
    if (await confirmation.isVisible()) await confirmation.click();
    await expect(main).toHaveURL(/\/auth\/logout\/success/);
    expect((await main.request.get('/api/me')).status()).toBe(401);
    await late.unrouteAll({ behavior: 'wait' });
    await main.getByRole('link', { name: 'Erneut anmelden' }).click();
    await main.locator('input[name=username]').fill(email);
    await main.locator('input[name=password]').fill(e2ePassword);
    await main.locator('button[type=submit]').click();
    await expect.poll(async () => (await main.request.get('/api/me')).status()).toBe(200);
  } finally {
    release();
    await context.close();
  }
}
