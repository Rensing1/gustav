import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("responsive workspace contract", () => {
  it("owns every shell width and the full-width body in the primitive layer", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const primitives = readFileSync(path.resolve(currentDir, "ui-primitives.css"), "utf8");
    const base = readFileSync(path.resolve(currentDir, "app.css"), "utf8");
    const tokens = readFileSync(path.resolve(currentDir, "theme-tokens.css"), "utf8");

    expect(tokens).toContain("--layout-compact-max: 42rem;");
    expect(tokens).toContain("--layout-content-max: 80rem;");
    expect(tokens).toContain("--layout-wide-max: 112rem;");
    expect(tokens).toContain("--layout-canvas-max: 144rem;");
    expect(tokens).toContain("--layout-reading-max: 68ch;");
    expect(tokens).toContain("--layout-form-max: 52rem;");
    expect(primitives).toMatch(/\.workspace-inner\s*\{[^}]*var\(--layout-content-max\)/s);
    expect(primitives).toMatch(/\.workspace-inner--compact\s*\{[^}]*var\(--layout-compact-max\)/s);
    expect(primitives).toMatch(/\.workspace-inner--wide\s*\{[^}]*var\(--layout-wide-max\)/s);
    expect(primitives).toMatch(/\.workspace-inner--canvas\s*\{[^}]*var\(--layout-canvas-max\)/s);
    expect(primitives).toMatch(/\.workspace-inner--auth\s*\{[^}]*38rem/s);
    expect(primitives).toMatch(/\.workspace-body\s*\{[^}]*width:\s*100%;[^}]*min-width:\s*0;/s);
    expect(primitives).not.toMatch(/\.workspace-body\s*\{[^}]*42rem/s);
    expect(base).not.toContain(".workspace-inner {");
    expect(base).not.toContain(".workspace-body {");
    expect(base).not.toContain(".workspace-inner--wide {");
  });

  it("keeps the teacher work starter aligned with the catalog measure", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const teaching = readFileSync(path.resolve(currentDir, "teaching-workspace.css"), "utf8");

    expect(teaching).toMatch(
      /\.teacher-home-workstarter\s*\{[^}]*width:\s*min\(100%,\s*var\(--layout-content-max\)\);[^}]*margin-inline:\s*auto;/s
    );
  });

  it("keeps learner lists adaptive and narrow content locally constrained", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const learning = readFileSync(path.resolve(currentDir, "learning-unit.css"), "utf8");
    const teaching = readFileSync(path.resolve(currentDir, "teaching-workspace.css"), "utf8");
    const layout = readFileSync(path.resolve(currentDir, "../../routes/+layout.svelte"), "utf8");

    expect(learning).toMatch(/\.learning-home\s*>\s*\.quiet-list,[\s\S]*?grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(min\(20rem,\s*100%\),\s*1fr\)\);/s);
    expect(learning).toMatch(/\.learning-portfolio\s*\{[^}]*width:\s*100%;[^}]*max-width:\s*64rem;[^}]*margin-inline:\s*auto;/s);
    expect(teaching).not.toMatch(/\.workspace-body\s*\{[^}]*width:/s);
    expect(layout).not.toContain("workspace-header--measure");
  });
});
