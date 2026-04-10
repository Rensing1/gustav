import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("register auth route contract", () => {
  it("uses the auth layout mode and a reduced register copy", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain("hidePageHeading: true");
    expect(serverSource).toContain("authLayout: true");
    expect(routeSource).toContain('title="Registrieren"');
    expect(routeSource).not.toContain("Schulzugang vorbereiten");
    expect(routeSource).not.toContain("Die eigentliche Registrierung und Verifizierung bleiben beim IdP.");
  });
});
