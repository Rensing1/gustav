import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const routesDir = path.dirname(fileURLToPath(import.meta.url));

function routeSource(relativePath: string): string {
  return readFileSync(path.resolve(routesDir, relativePath), "utf8");
}

describe("workspace layout route contract", () => {
  it("uses standard as the default application workspace", () => {
    expect(routeSource("+layout.server.ts")).toContain('workspaceLayout: "standard"');
  });

  it("keeps intentionally narrow pages compact", () => {
    expect(routeSource("profile/+page.server.ts")).toContain('workspaceLayout: "compact"');
    expect(routeSource("learning/kummerkasten/+page.server.ts")).toContain('workspaceLayout: "compact"');
    expect(routeSource("teaching/kummerkasten/+page.server.ts")).toContain('workspaceLayout: "compact"');
  });

  it("maps existing large workspaces to semantic modes", () => {
    expect(routeSource("teaching/units/+page.server.ts")).toContain('workspaceLayout: "wide"');
    expect(routeSource("live/+page.server.ts")).toContain('workspaceLayout: "canvas"');
    expect(routeSource("teaching/units/+page.server.ts")).not.toContain("wideWorkspaceShell");
    expect(routeSource("live/+page.server.ts")).not.toContain("wideWorkspaceShell");
  });
});
