import { expect, test, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";

const password = "Passw0rd!e2e";

async function openUiLab(page: Page, viewport: { width: number; height: number }): Promise<void> {
  const unique = `${viewport.width}_${viewport.height}_${Date.now()}`;
  const email = `visual_design_${unique}@${emailDomain}`;
  await ensureTeacherUser(email, password);
  await page.setViewportSize(viewport);
  await login(page, email, password);
  await page.goto("/ui-lab");
  await expect(page.getByRole("heading", { name: "Designsystem-Vorschau für GUSTAV" })).toBeVisible();

  // Screenshots must not race the locally bundled product fonts.
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function expectContrastDesignContract(page: Page): Promise<void> {
  const contract = await page.locator(".preview-page").evaluate((preview) => {
    const previewStyle = getComputedStyle(preview);
    const heading = preview.querySelector(".preview-heading h1");
    const currentButton = preview.querySelector('.preview-theme-toggle button[data-current="true"]');
    const card = preview.querySelector(".preview-card");

    if (!(heading instanceof HTMLElement) || !(currentButton instanceof HTMLElement) || !(card instanceof HTMLElement)) {
      throw new Error("UI lab is missing a representative contrast-design element");
    }

    const headingStyle = getComputedStyle(heading);
    const buttonStyle = getComputedStyle(currentButton);
    const cardStyle = getComputedStyle(card);

    return {
      accent: previewStyle.getPropertyValue("--color-accent").trim(),
      background: previewStyle.getPropertyValue("--color-bg-base").trim(),
      border: previewStyle.getPropertyValue("--color-border").trim(),
      radius: previewStyle.getPropertyValue("--radius-m").trim(),
      shadow: previewStyle.getPropertyValue("--color-shadow").trim(),
      headingFont: headingStyle.fontFamily,
      bodyFont: previewStyle.fontFamily,
      buttonRadius: buttonStyle.borderRadius,
      buttonShadow: buttonStyle.boxShadow,
      cardRadius: cardStyle.borderRadius,
      cardBorderStyle: cardStyle.borderTopStyle,
      cardBorderWidth: cardStyle.borderTopWidth
    };
  });

  expect(contract.accent).toBe("#ff512f");
  expect(contract.background).toBe("#f9f9f9");
  expect(contract.border).toBe("#1b1b1b");
  expect(contract.radius).toBe("0");
  expect(contract.shadow).toContain("4px 4px 0 0");
  expect(contract.shadow).toContain("27, 27, 27");
  expect(contract.headingFont).toContain("Space Grotesk");
  expect(contract.bodyFont).toContain("Inter");
  expect(contract.buttonRadius).toBe("0px");
  expect(contract.buttonShadow).toContain("4px 4px 0px");
  expect(contract.cardRadius).toBe("0px");
  expect(contract.cardBorderStyle).toBe("solid");
  expect(contract.cardBorderWidth).toBe("2px");

  const topbarControls = await page.locator(".app-topbar-tools").evaluate((tools) => {
    const themeToggle = tools.querySelector(".theme-toggle");
    const accountTrigger = tools.querySelector(".account-trigger");
    if (!(themeToggle instanceof HTMLElement) || !(accountTrigger instanceof HTMLElement)) {
      throw new Error("Top bar is missing its theme or account control");
    }

    const chrome = (element: HTMLElement) => {
      const style = getComputedStyle(element);
      return {
        background: style.backgroundColor,
        borderColor: style.borderTopColor,
        borderRadius: style.borderRadius,
        borderStyle: style.borderTopStyle,
        borderWidth: style.borderTopWidth,
        boxShadow: style.boxShadow
      };
    };

    return {
      account: chrome(accountTrigger),
      theme: chrome(themeToggle)
    };
  });
  expect(topbarControls.theme).toEqual(topbarControls.account);
}

test.describe("@visual-smoke @design-system contrast design contract", () => {
  for (const viewport of [
    { name: "desktop", width: 1440, height: 900 },
    { name: "mobile", width: 390, height: 844 }
  ]) {
    test(`keeps approved light and dark baselines on ${viewport.name}`, async ({ page }) => {
      await openUiLab(page, viewport);
      await expectContrastDesignContract(page);
      await expect(page).toHaveScreenshot(`ui-lab-light-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide"
      });

      await page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
      await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
      await page.getByRole("button", { name: "Dark", exact: true }).click();
      await expect(page.locator(".preview-page")).toHaveAttribute("data-theme", "dark");
      await page.evaluate(() => window.scrollTo(0, 0));

      const darkContract = await page.locator(".preview-page").evaluate((preview) => {
        const style = getComputedStyle(preview);
        return {
          background: style.getPropertyValue("--color-bg-base").trim(),
          border: style.getPropertyValue("--color-border").trim(),
          shadow: style.getPropertyValue("--color-shadow").trim()
        };
      });
      expect(darkContract.background).toBe("#121212");
      expect(darkContract.border).toBe("#f0f1f1");
      expect(darkContract.shadow).toContain("4px 4px 0 0");
      expect(darkContract.shadow).toContain("240, 241, 241");
      await expect(page).toHaveScreenshot(`ui-lab-dark-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide"
      });
    });
  }
});
