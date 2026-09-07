import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("shared graph presentation", () => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  it("uses the same viewport controller without enabling learner editing", () => {
    const learning = readFileSync(path.resolve(currentDir, "LearningUnitOverview.svelte"), "utf8");
    const teaching = readFileSync(path.resolve(currentDir, "../../../routes/teaching/units/[unitId]/+page.svelte"), "utf8");
    for (const source of [learning, teaching]) {
      expect(source).toContain('$lib/components/ui/GraphViewportControls.svelte');
      expect(source).toContain("<GraphViewportControls");
    }
    expect(learning).not.toContain("fitViewOptions=");
    expect(learning).toContain("nodesConnectable={false}");
    expect(learning).toContain("nodesDraggable={false}");
  });

  it("uses the same compact card spacing for both roles", () => {
    for (const name of ["./LearningGraphNode.svelte", "../teacher-unit-graph/GraphUnitNode.svelte"]) {
      const source = readFileSync(path.resolve(currentDir, name), "utf8");
      expect(source).toContain("class:teacher-flow-unit-node--compact={data.compact}");
    }
  });
});
