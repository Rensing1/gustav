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

async function expectDialogDesignContract(page: Page, layoutMode: "desktop" | "tablet" | "mobile"): Promise<void> {
  const contract = await page.getByTestId("preview-dialog-conversation").evaluate((workspace) => {
    const layout = workspace.querySelector(".dialog-layout");
    const sidebar = workspace.querySelector(".dialog-sidebar");
    const main = workspace.querySelector(".dialog-main");
    const transcript = workspace.querySelector(".dialog-transcript");
    const aiMessage = workspace.querySelector(".dialog-message--ai");
    const studentMessage = workspace.querySelector(".dialog-message--student");
    const starter = workspace.querySelector(".dialog-starter");
    const sessionActions = workspace.querySelector(".dialog-session-actions");
    const composer = workspace.querySelector(".dialog-composer");
    const sendButton = workspace.querySelector(".dialog-composer__actions .workspace-top-action--accent");
    if (
      !(layout instanceof HTMLElement) ||
      !(sidebar instanceof HTMLElement) ||
      !(main instanceof HTMLElement) ||
      !(transcript instanceof HTMLElement) ||
      !(aiMessage instanceof HTMLElement) ||
      !(studentMessage instanceof HTMLElement) ||
      !(starter instanceof HTMLElement) ||
      !(sessionActions instanceof HTMLElement) ||
      !(composer instanceof HTMLElement) ||
      !(sendButton instanceof HTMLElement)
    ) {
      throw new Error("UI lab is missing a representative dialog element");
    }

    const layoutStyle = getComputedStyle(layout);
    const sidebarStyle = getComputedStyle(sidebar);
    const transcriptStyle = getComputedStyle(transcript);
    const aiStyle = getComputedStyle(aiMessage);
    const studentStyle = getComputedStyle(studentMessage);
    const starterStyle = getComputedStyle(starter);
    const workspaceBox = workspace.getBoundingClientRect();
    const layoutBox = layout.getBoundingClientRect();
    const sidebarBox = sidebar.getBoundingClientRect();
    const mainBox = main.getBoundingClientRect();
    const sessionActionsBox = sessionActions.getBoundingClientRect();
    const composerBox = composer.getBoundingClientRect();
    const sendButtonBox = sendButton.getBoundingClientRect();
    const transcriptContentWidth =
      transcript.clientWidth -
      Number.parseFloat(transcriptStyle.paddingLeft) -
      Number.parseFloat(transcriptStyle.paddingRight);

    return {
      workspaceWidth: workspaceBox.width,
      layoutColumns: layoutStyle.gridTemplateColumns,
      sidebarAreas: sidebarStyle.gridTemplateAreas,
      sidebarPosition: sidebarStyle.position,
      layoutBox: { x: layoutBox.x, y: layoutBox.y, width: layoutBox.width, height: layoutBox.height },
      sidebarBox: { x: sidebarBox.x, y: sidebarBox.y, width: sidebarBox.width, height: sidebarBox.height },
      mainBox: { x: mainBox.x, y: mainBox.y, width: mainBox.width, height: mainBox.height },
      sessionActionsBox: {
        x: sessionActionsBox.x,
        y: sessionActionsBox.y,
        width: sessionActionsBox.width,
        height: sessionActionsBox.height
      },
      composerContentWidth: composerBox.width - 2 * Number.parseFloat(getComputedStyle(composer).borderLeftWidth) -
        Number.parseFloat(getComputedStyle(composer).paddingLeft) - Number.parseFloat(getComputedStyle(composer).paddingRight),
      sendButtonWidth: sendButtonBox.width,
      transcriptBorderStyle: transcriptStyle.borderTopStyle,
      transcriptBorderWidth: transcriptStyle.borderTopWidth,
      transcriptRadius: transcriptStyle.borderRadius,
      transcriptContentWidth,
      aiBackground: aiStyle.backgroundColor,
      aiLeftBorderWidth: aiStyle.borderLeftWidth,
      aiWidth: aiMessage.getBoundingClientRect().width,
      studentBackground: studentStyle.backgroundColor,
      studentRightBorderWidth: studentStyle.borderRightWidth,
      studentJustify: studentStyle.justifySelf,
      studentWidth: studentMessage.getBoundingClientRect().width,
      starterRadius: starterStyle.borderRadius
    };
  });

  expect(contract.transcriptBorderStyle).toBe("none");
  expect(contract.transcriptBorderWidth).toBe("0px");
  expect(contract.transcriptRadius).toBe("0px");
  expect(contract.aiBackground).toBe(contract.studentBackground);
  expect(contract.aiLeftBorderWidth).toBe("4px");
  expect(contract.studentRightBorderWidth).toBe("4px");
  expect(contract.studentJustify).toBe("end");
  expect(contract.starterRadius).toBe("0px");

  if (layoutMode === "desktop") {
    expect(contract.workspaceWidth).toBeGreaterThanOrEqual(1024);
    expect(contract.mainBox.x).toBeGreaterThan(contract.sidebarBox.x + contract.sidebarBox.width - 1);
    expect(contract.sidebarPosition).toBe("sticky");
    expect(contract.layoutColumns.split(" ")).toHaveLength(2);
    expect(contract.sidebarBox.y).toBe(contract.mainBox.y);
    expect(contract.sidebarBox.y + contract.sidebarBox.height - contract.sessionActionsBox.y - contract.sessionActionsBox.height).toBeLessThanOrEqual(17);
    expect(contract.aiWidth).toBeLessThan(contract.transcriptContentWidth);
    expect(contract.studentWidth).toBeLessThan(contract.transcriptContentWidth);
    expect(contract.sendButtonWidth).toBeLessThan(contract.composerContentWidth);
  } else if (layoutMode === "tablet") {
    expect(contract.workspaceWidth).toBeGreaterThanOrEqual(680);
    expect(contract.workspaceWidth).toBeLessThan(1024);
    expect(contract.mainBox.y).toBeGreaterThan(contract.sidebarBox.y + contract.sidebarBox.height - 1);
    expect(contract.sidebarAreas).toContain("context meta actions");
    expect(contract.aiWidth).toBeLessThan(contract.transcriptContentWidth);
    expect(contract.studentWidth).toBeLessThan(contract.transcriptContentWidth);
    expect(contract.sendButtonWidth).toBeLessThan(contract.composerContentWidth);
  } else {
    expect(contract.workspaceWidth).toBeLessThan(680);
    expect(contract.mainBox.y).toBeGreaterThan(contract.sidebarBox.y + contract.sidebarBox.height - 1);
    expect(contract.sidebarAreas).toContain("context");
    expect(Math.abs(contract.aiWidth - contract.transcriptContentWidth)).toBeLessThanOrEqual(1);
    expect(Math.abs(contract.studentWidth - contract.transcriptContentWidth)).toBeLessThanOrEqual(1);
    expect(
      Math.abs(contract.sendButtonWidth - contract.composerContentWidth),
      `mobile dialog geometry: ${JSON.stringify(contract)}`
    ).toBeLessThanOrEqual(1);
  }

  const closingShadow = await page.getByTestId("preview-dialog-completion").locator(".dialog-closing").evaluate((closing) => {
    return getComputedStyle(closing).boxShadow;
  });
  expect(closingShadow).toContain("4px 4px 0px");
}

async function expectDialogStatesScreenshot(page: Page, name: string): Promise<void> {
  // The sticky product top bar would otherwise cover the isolated component after Playwright scrolls it into view.
  const isolationStyle = await page.addStyleTag({ content: ".app-topbar { display: none !important; }" });
  try {
    await expect(page.getByTestId("preview-dialog-states")).toHaveScreenshot(name, {
      animations: "disabled",
      caret: "hide"
    });
  } finally {
    await isolationStyle.evaluate((style) => style.remove());
  }
}

test.describe("@visual-smoke @design-system contrast design contract", () => {
  for (const viewport of [
    { name: "desktop", width: 1440, height: 900 },
    { name: "tablet", width: 1024, height: 768 },
    { name: "mobile", width: 390, height: 844 }
  ] as const) {
    test(`keeps approved light and dark baselines on ${viewport.name}`, async ({ page }) => {
      await openUiLab(page, viewport);
      await expectContrastDesignContract(page);
      await expectDialogDesignContract(page, viewport.name);
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
      await expectDialogDesignContract(page, viewport.name);
      await expect(page).toHaveScreenshot(`ui-lab-dark-${viewport.name}.png`, {
        animations: "disabled",
        caret: "hide"
      });
      await expectDialogStatesScreenshot(page, `dialog-states-dark-${viewport.name}.png`);

      await page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
      await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "light");
      await page.getByRole("button", { name: "Light", exact: true }).click();
      await expect(page.locator(".preview-page")).toHaveAttribute("data-theme", "light");
      await expectDialogStatesScreenshot(page, `dialog-states-light-${viewport.name}.png`);
    });
  }
});
