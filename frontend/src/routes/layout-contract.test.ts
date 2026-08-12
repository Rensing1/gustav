import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("root layout contract", () => {
  it("lets routes request the wide workspace shell through page data", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain("function routeRequestsWideWorkspaceShell(): boolean");
    expect(layoutSource).toContain('return page.data.wideWorkspaceShell === true;');
    expect(layoutSource).toContain(
      "return routeRequestsWideWorkspaceShell() || isTeacherUnitWorkspaceRoute() || isLearnerUnitWorkspaceRoute();"
    );
  });

  it("uses a dedicated wide workspace shell for the live route", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain("function routeRequestsLiveWorkspaceShell(): boolean");
    expect(layoutSource).toContain("return /^\\/live(?:$|\\/|\\?)/.test(page.url.pathname);");
    expect(layoutSource).toContain("class:workspace-inner--live-wide={hasLiveWorkspaceShell()}");
  });

  it("always exposes practice navigation to learners", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain('href: "/learning/practice"');
    expect(layoutSource).not.toContain("requiresPractice");
    expect(layoutSource).not.toContain("practice_enabled");
  });
});
