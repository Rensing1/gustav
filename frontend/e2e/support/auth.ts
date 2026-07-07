import { expect, type Page } from "@playwright/test";

import { webBase } from "./e2e-env";

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/auth/login");
  await page.locator('input[name="username"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"], input[type="submit"]').first().click();
  await expect
    .poll(async () => {
      const response = await page.request.get(`${webBase}/api/me`);
      return response.status();
    }, { timeout: 30_000 })
    .toBe(200);
}

export async function currentUserSub(page: Page): Promise<string> {
  const response = await page.request.get(`${webBase}/api/me`);
  expect(response.ok(), await response.text()).toBe(true);
  const payload = await response.json();
  expect(typeof payload.sub).toBe("string");
  return payload.sub;
}
