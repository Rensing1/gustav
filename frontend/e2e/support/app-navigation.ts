import { expect, type Page } from "@playwright/test";

/** Use the account menu like a person would; keep it closed during layout checks. */
export async function setAppTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  const shell = page.locator(".app-shell");
  if (await shell.getAttribute("data-theme") === theme) return;
  await page.getByLabel("Konto-Menü", { exact: true }).click();
  await page.getByRole("button", {
    name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true
  }).click();
  await expect(shell).toHaveAttribute("data-theme", theme);
  await page.keyboard.press("Escape");
}

export async function openAppDestination(page: Page, name: string): Promise<void> {
  const targets: Record<string, string> = { Live: "/live", Kurse: "/teaching/courses", Lerneinheiten: "/teaching/units" };
  if (new URL(page.url()).pathname === targets[name]) return;
  const direct = page.getByRole("link", { name, exact: true });
  if (!(await direct.isVisible())) {
    const context = page.locator(".context-header__location > summary");
    if (await context.isVisible()) await context.click();
    else await page.locator(".global-header__mobile-menu > summary").click();
  }
  await page.getByRole("link", { name, exact: true }).click();
}
