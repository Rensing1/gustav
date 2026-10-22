import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync("src/routes/live/LiveTaskStrip.svelte", "utf8");
const tokens = readFileSync("src/lib/styles/theme-tokens.css", "utf8");

describe("numbered Live strip design", () => {
  it("keeps touch targets and selection independent of the assessment fill", () => {
    expect(source).toContain("grid-template-columns: repeat(auto-fill, 2.75rem)");
    expect(source).toContain("min-height: 2.75rem");
    expect(source).toContain("outline-offset: 2px");
    expect(source).not.toContain("is-latest::after");
  });
  it("uses the documented assessment palette from shared theme tokens", () => {
    for (const level of ["zero", "low", "mid", "high"]) {
      expect(source).toContain(`background: var(--color-live-score-${level})`);
      expect(source).toContain(`color: var(--color-live-on-${level})`);
    }
    for (const color of ["#7a0000", "#c62828", "#d87a00", "#2f8f5b", "#ff4d4d", "#ff6b57", "#ff9a2f", "#49b36f"]) {
      expect(tokens).toContain(color);
      expect(source).not.toContain(color);
    }
    expect(source).toContain("border: 1px dashed var(--color-control-border)");
    expect(source).toContain("background: var(--color-info-soft)");
  });
});
