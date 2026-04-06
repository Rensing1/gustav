import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher unit graph route contract", () => {
  it("uses shared workspace controls and no longer depends on legacy app.css popover styles", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const graphNodeSource = readFileSync(
      path.resolve(currentDir, "../../../../lib/components/teacher-unit-graph/GraphUnitNode.svelte"),
      "utf8"
    );
    const appCss = readFileSync(path.resolve(currentDir, "../../../../lib/styles/app.css"), "utf8");

    expect(routeSource).toContain("<GraphInspectorPanel");
    expect(routeSource).toContain('class="workspace-unit-commandbar-popover"');
    expect(routeSource).toContain('class="workspace-field"');
    expect(graphNodeSource).toContain('class="teacher-flow-unit-node__quickedit-field workspace-field"');
    expect(appCss).not.toContain(".workspace-unit-commandbar-popover {");
    expect(appCss).not.toContain(".teacher-flow-unit-node__quickedit {");
  });
});
