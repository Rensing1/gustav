import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher node editor contract", () => {
  it("uses shared workspace controls from the design system", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");

    expect(routeSource).toContain('class="workspace-field"');
    expect(routeSource).toContain('class="workspace-link-action"');
    expect(routeSource).toContain('class="workspace-node-editor-section-action"');
    expect(appCss).not.toContain(".workspace-field {");
    expect(appCss).not.toContain(".workspace-button {");
  });
});
