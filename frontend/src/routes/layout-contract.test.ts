import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("root layout contract", () => {
  it("uses the typed workspace layout supplied through page data", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain("function workspaceLayout(): WorkspaceLayout");
    expect(layoutSource).toContain('return page.data.workspaceLayout ?? "standard";');
    expect(layoutSource).toContain('class:workspace-inner--compact={workspaceLayout() === "compact"}');
    expect(layoutSource).toContain('class:workspace-inner--wide={workspaceLayout() === "wide"}');
    expect(layoutSource).toContain('class:workspace-inner--canvas={workspaceLayout() === "canvas"}');
    expect(layoutSource).not.toContain("wideWorkspaceShell");
    expect(layoutSource).not.toContain("routeRequestsLiveWorkspaceShell");
    expect(layoutSource).not.toContain("isLearnerUnitWorkspaceRoute() ||");
  });

  it("always exposes practice navigation to learners", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain('href: "/learning/practice"');
    expect(layoutSource).not.toContain("requiresPractice");
    expect(layoutSource).not.toContain("practice_enabled");
  });
});
