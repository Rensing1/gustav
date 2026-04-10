import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("LearningGraphNode contract", () => {
  it("keeps the learner node status mapping and selected-state hook", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const componentSource = readFileSync(path.resolve(currentDir, "LearningGraphNode.svelte"), "utf8");
    const css = readFileSync(path.resolve(currentDir, "../../styles/design-system.css"), "utf8");

    expect(componentSource).toContain('class={`teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-${data.status ?? "locked"}`}');
    expect(componentSource).toContain("class:teacher-flow-unit-node--selected={selected}");
    expect(componentSource).not.toContain("teacher-flow-unit-node__state");

    expect(css).toMatch(/\.teacher-flow-unit-node--learner-open\s*\{[^}]*border-color:\s*var\(--color-border\);/s);
    expect(css).toMatch(/\.teacher-flow-unit-node--learner-done\s*\{[^}]*border-color:\s*var\(--color-success\);/s);
    expect(css).toMatch(/\.teacher-flow-unit-node--learner-done[\s\S]*box-shadow:\s*var\(--color-shadow\);/s);
    expect(css).toMatch(/\.teacher-flow-unit-node--learner-locked[\s\S]*opacity:\s*0\.56;/s);
    expect(css).toMatch(/\.teacher-flow-unit-node--selected\.teacher-flow-unit-node--learner[\s\S]*border-color:\s*var\(--color-accent\);/s);
    expect(css).toMatch(/\.teacher-flow-unit-node--learner-done \.teacher-flow-unit-node__copy strong[\s\S]*var\(--color-success\)/s);
  });
});
