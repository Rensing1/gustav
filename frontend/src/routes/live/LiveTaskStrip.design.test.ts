import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync("src/routes/live/LiveTaskStrip.svelte", "utf8");

describe("original compact Live strip design", () => {
  it("retains the dense original grid at every breakpoint", () => {
    expect(source).toContain("grid-template-columns: repeat(auto-fit, minmax(0.7rem, 0.9rem))");
    expect(source).toContain("gap: 0.28rem");
    expect(source).toContain("width: 0.85rem");
    expect(source).toContain("min-height: 1.15rem");
    expect(source).not.toContain("@media");
    expect(source).not.toContain("live-task-strip__swatch");
  });
  it("preserves separate original score colors in both themes", () => {
    for (const color of ["#7a0000", "#c62828", "#d87a00", "#2f8f5b", "#ff4d4d", "#ff6b57", "#ff9a2f", "#49b36f"]) {
      expect(source).toContain(color);
    }
    expect(source).toContain("outline-offset: -2px");
    expect(source).toContain(".live-task-strip__item.is-latest::after");
  });
});
