import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("root auth route contract", () => {
  it("uses the auth layout mode and a reduced landing copy", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain("hidePageHeading: true");
    expect(serverSource).toContain("authLayout: true");
    expect(routeSource).toContain('title="Anmelden"');
    expect(routeSource).toContain('data.reason === "session-expired"');
    expect(routeSource).toContain('data.reason === "session_expired"');
    expect(routeSource).toContain("Sitzung abgelaufen. Nach der Anmeldung geht es direkt zurück.");
    expect(routeSource).not.toContain("Eine Oberfläche. Klare Anmeldung.");
    expect(routeSource).not.toContain("Der Einstieg bleibt in der App ruhig und präzise.");
  });
});
