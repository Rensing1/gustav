import { expect, type Locator } from "@playwright/test";

/** Measure composited CSS colors, including color-mix and translucent states. */
export async function expectDesignContrast(elements: Locator, includeDisabled = false) {
  const failures = await elements.evaluateAll((nodes, includeDisabled) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d")!;
    const luminance = (rgb: Uint8ClampedArray) => {
      const [r, g, b] = [...rgb].slice(0, 3).map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    return nodes.filter((node) => node.getClientRects().length && (node.textContent?.trim() || node.hasAttribute("aria-label") || node instanceof HTMLInputElement) && (includeDisabled || !node.closest('[disabled], [aria-disabled="true"]')) && getComputedStyle(node).visibility === "visible").flatMap((node) => {
      const ancestors: Element[] = [];
      for (let parent: Element | null = node; parent; parent = parent.parentElement) ancestors.unshift(parent);
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--color-bg-base");
      ctx.fillRect(0, 0, 1, 1);
      for (const ancestor of ancestors) { ctx.fillStyle = getComputedStyle(ancestor).backgroundColor; ctx.fillRect(0, 0, 1, 1); }
      const bg = luminance(ctx.getImageData(0, 0, 1, 1).data);
      ctx.fillStyle = getComputedStyle(node).color;
      ctx.fillRect(0, 0, 1, 1);
      const fg = luminance(ctx.getImageData(0, 0, 1, 1).data);
      const ratio = (Math.max(bg, fg) + 0.05) / (Math.min(bg, fg) + 0.05);
      return ratio < 4.5 ? [{ tag: node.tagName, classes: node.className, text: node.textContent?.trim().slice(0, 60), ratio }] : [];
    });
  }, includeDisabled);
  expect(failures).toEqual([]);
}
