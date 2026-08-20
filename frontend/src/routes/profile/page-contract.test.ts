import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("profile route contract", () => {
  it("uses the shared page head and profile editor component", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(routeSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(routeSource).toContain('import ProfileEditor from "$lib/components/profile/ProfileEditor.svelte";');
    expect(routeSource).toContain("<PageActionHead");
    expect(routeSource).toContain("<ProfileEditor");
    expect(serverSource).toContain('"/api/app/profile"');
    expect(serverSource).toContain('"/api/app/profile/cli-tokens"');
    expect(serverSource).toContain('profile.user.roles.includes("teacher")');
    expect(serverSource).toContain("createCliToken");
    expect(serverSource).toContain("revokeCliToken");
    expect(serverSource).toContain("includeSameOrigin: true");
    expect(serverSource).toContain("hidePageHeading: true");
  });
});
