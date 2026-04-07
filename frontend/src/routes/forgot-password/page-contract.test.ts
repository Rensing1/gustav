import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("forgot-password auth route contract", () => {
  it("uses the auth layout mode and a reduced reset copy", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain("hidePageHeading: true");
    expect(serverSource).toContain("authLayout: true");
    expect(routeSource).toContain('title="Passwort zurücksetzen"');
    expect(routeSource).not.toContain("Reset sicher anstoßen");
    expect(routeSource).not.toContain("GUSTAV sammelt optional die Schul-E-Mail");
  });
});
