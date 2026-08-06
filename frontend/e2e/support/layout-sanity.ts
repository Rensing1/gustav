import { expect, type Locator, type Page } from "@playwright/test";

export type SmokePage = {
  path: string;
  heading: string;
};

export async function expectVisiblePageShell(page: Page, smokePage: SmokePage): Promise<void> {
  await page.goto(smokePage.path);
  await expect(page.getByRole("heading", { name: smokePage.heading })).toBeVisible();
  await expect(page.locator("body")).toContainText("GUSTAV");
  await expectInteractiveSurface(page.locator("body"));
  await expectNoViewportOverflow(page);
}

export async function expectInteractiveSurface(locator: Locator): Promise<void> {
  const metrics = await locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const visibleElements = [...element.querySelectorAll("a, button, input, form, main, section, [role='button']")]
      .filter((candidate) => {
        const rect = candidate.getBoundingClientRect();
        const styles = window.getComputedStyle(candidate);
        return rect.width > 0 && rect.height > 0 && styles.visibility !== "hidden" && styles.display !== "none";
      })
      .length;

    return {
      textLength: (element as HTMLElement).innerText.trim().length,
      width: box.width,
      height: box.height,
      visibleElements
    };
  });

  expect(metrics.textLength).toBeGreaterThan(20);
  expect(metrics.width).toBeGreaterThan(300);
  expect(metrics.height).toBeGreaterThan(200);
  expect(metrics.visibleElements).toBeGreaterThan(1);
}

export async function expectNoViewportOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return {
      horizontalOverflow: doc.scrollWidth - doc.clientWidth,
      bodyWidth: document.body.getBoundingClientRect().width,
      viewportWidth: window.innerWidth
    };
  });

  expect(overflow.horizontalOverflow).toBeLessThanOrEqual(4);
  expect(overflow.bodyWidth).toBeLessThanOrEqual(overflow.viewportWidth + 4);
}

function normalizedColorChannels(color: string): number[] {
  const hex = color.trim().match(/^#([0-9a-f]{6})$/i)?.[1];
  if (hex) {
    return [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255);
  }
  const channels = color.match(/\d*\.?\d+/g)?.slice(0, 3).map(Number) ?? [];
  if (channels.some((channel) => channel > 1)) {
    return channels.map((channel) => channel / 255);
  }
  return channels;
}

function relativeLuminance(color: string): number {
  const channels = normalizedColorChannels(color).map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  );
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrastRatio(foreground: string, background: string): number {
  const light = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const dark = Math.min(relativeLuminance(foreground), relativeLuminance(background));
  return (light + 0.05) / (dark + 0.05);
}

export async function expectLearnerMaterialContrast(page: Page): Promise<void> {
  const palette = await page.evaluate(() => {
    const context = document.querySelector(".learner-task-context");
    const title = document.querySelector(".learner-reference-document__toggle strong");
    const moduleTitle = document.querySelector(".learner-material-context__module-toggle h4");
    if (!(context instanceof HTMLElement) || !(title instanceof HTMLElement) || !(moduleTitle instanceof HTMLElement)) {
      throw new Error("Learner material surfaces are incomplete");
    }
    const rootStyles = getComputedStyle(document.documentElement);
    return {
      background: rootStyles.getPropertyValue("--color-bg-base").trim(),
      title: getComputedStyle(title).color,
      moduleTitle: getComputedStyle(moduleTitle).color,
      contextWidth: context.getBoundingClientRect().width,
      contextScrollWidth: context.scrollWidth
    };
  });

  expect(contrastRatio(palette.title, palette.background)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(palette.moduleTitle, palette.background)).toBeGreaterThanOrEqual(4.5);
  expect(palette.contextScrollWidth).toBeLessThanOrEqual(palette.contextWidth + 1);
}

export async function expectLearnerTaskTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  const palette = await page.evaluate(() => {
    const topbar = document.querySelector(".app-topbar--learner-unit");
    const brand = document.querySelector(".app-topbar--learner-unit .brand-copy strong");
    const editor = document.querySelector(".learning-markdown-editor");
    const toolbar = document.querySelector(".learning-markdown-editor__toolbar");
    const surface = document.querySelector(".learning-markdown-editor__surface");
    const control = document.querySelector(".learning-markdown-editor__toolbar button");
    if (
      !(topbar instanceof HTMLElement) ||
      !(brand instanceof HTMLElement) ||
      !(editor instanceof HTMLElement) ||
      !(toolbar instanceof HTMLElement) ||
      !(surface instanceof HTMLElement) ||
      !(control instanceof HTMLElement)
    ) {
      throw new Error("Learner task theme surfaces are incomplete");
    }

    const toolbarBox = toolbar.getBoundingClientRect();
    return {
      topbarBackground: getComputedStyle(topbar).backgroundColor,
      editorBackground: getComputedStyle(editor).backgroundColor,
      toolbarBackground: getComputedStyle(toolbar).backgroundColor,
      surfaceBackground: getComputedStyle(surface).backgroundColor,
      controlBackground: getComputedStyle(control).backgroundColor,
      controlShadow: getComputedStyle(control).boxShadow,
      controlRadius: getComputedStyle(control).borderRadius,
      toolbarWidth: toolbarBox.width,
      toolbarScrollWidth: toolbar.scrollWidth
    };
  });

  for (const color of [
    palette.topbarBackground,
    palette.editorBackground,
    palette.toolbarBackground,
    palette.surfaceBackground,
    palette.controlBackground
  ]) {
    const channels = normalizedColorChannels(color);
    expect(channels).toHaveLength(3);
    if (theme === "dark") {
      expect(Math.max(...channels), `${color} should be a dark theme surface`).toBeLessThan(0.25);
    } else {
      expect(Math.min(...channels), `${color} should be a light theme surface`).toBeGreaterThan(0.85);
    }
  }

  if (theme === "dark") {
    await expect.poll(async () => {
      const color = await page.locator(".app-topbar--learner-unit .brand-copy strong").evaluate((brand) => {
        return getComputedStyle(brand).color;
      });
      return Math.min(...normalizedColorChannels(color));
    }).toBeGreaterThan(0.75);
  } else {
    await expect.poll(async () => {
      const color = await page.locator(".app-topbar--learner-unit .brand-copy strong").evaluate((brand) => {
        return getComputedStyle(brand).color;
      });
      return Math.max(...normalizedColorChannels(color));
    }).toBeLessThan(0.25);
  }
  expect(palette.controlShadow).toBe("none");
  expect(palette.controlRadius).toBe("0px");
  expect(palette.toolbarScrollWidth).toBeLessThanOrEqual(palette.toolbarWidth + 1);
}
