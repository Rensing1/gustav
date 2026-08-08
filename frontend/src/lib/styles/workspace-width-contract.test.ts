import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("wide workspace contract", () => {
  it("owns base and wide workspace widths in the same primitive layer", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const primitives = readFileSync(path.resolve(currentDir, "ui-primitives.css"), "utf8");
    const base = readFileSync(path.resolve(currentDir, "app.css"), "utf8");

    const baseRule = primitives.indexOf(".workspace-inner {");
    const wideRule = primitives.indexOf(".workspace-inner--wide {");

    expect(baseRule).toBeGreaterThanOrEqual(0);
    expect(wideRule).toBeGreaterThan(baseRule);
    expect(primitives.slice(wideRule)).toMatch(/\.workspace-inner--wide\s*\{[^}]*112rem/s);
    expect(base).not.toContain(".workspace-inner--wide {");
  });

  it("keeps the teacher work starter aligned with the catalog measure", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const teaching = readFileSync(path.resolve(currentDir, "teaching-workspace.css"), "utf8");

    expect(teaching).toMatch(
      /\.teacher-home-workstarter\s*\{[^}]*width:\s*min\(100%,\s*var\(--layout-content-max\)\);[^}]*margin-inline:\s*auto;/s
    );
  });
});
