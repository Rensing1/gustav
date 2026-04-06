import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("learning unit route contract", () => {
  it("uses the shared workspace settings menu instead of the local legacy layout menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");

    expect(routeSource).toContain('import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";');
    expect(routeSource).toContain("<WorkspaceSettingsMenu");
    expect(routeSource).not.toContain("learning-unit-layout-menu");
    expect(appCss).not.toContain(".learning-unit-layout-menu");
  });

  it("keeps pane item lists intact while tracking a single inline submission focus", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("function setSubmissionWorkspace");
    expect(routeSource).toContain("left: paneId === \"left\" ? { itemKey, mode } : { itemKey: null, mode: null }");
    expect(routeSource).toContain("right: paneId === \"right\" ? { itemKey, mode } : { itemKey: null, mode: null }");
    expect(routeSource).not.toContain("focus.left.itemKey ? leftEntries.filter");
    expect(routeSource).not.toContain("focus.right.itemKey ? rightEntries.filter");
  });
});
