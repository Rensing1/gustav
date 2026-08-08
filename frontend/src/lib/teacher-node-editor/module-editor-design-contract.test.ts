import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const pageSource = readFileSync(path.resolve(currentDir, "../../routes/teaching/units/[unitId]/nodes/[nodeId]/+page.svelte"), "utf8");
const cssSource = readFileSync(path.resolve(currentDir, "../styles/teaching-workspace.css"), "utf8");

describe("module editor design contract", () => {
  it("keeps all productive workbench styles in the teaching layer", () => {
    expect(pageSource).not.toContain("<style");
    expect(cssSource).toContain(".teacher-module-workbench");
    expect(cssSource).toContain("container-type: inline-size");
  });

  it("switches from two flat areas to full-width stages at the component boundary", () => {
    expect(cssSource).toMatch(/@container\s+\(max-width:\s*63\.99rem\)/);
    expect(cssSource).toContain('[data-module-stage="contents"]');
    expect(cssSource).toContain('[data-module-stage="editor"]');
  });

  it("keeps material and task groups separate and provides keyboard reorder actions", () => {
    expect(pageSource).toContain('id="module-materials-heading"');
    expect(pageSource).toContain('id="module-tasks-heading"');
    expect(pageSource).toContain("Nach oben");
    expect(pageSource).toContain("Nach unten");
  });
});
