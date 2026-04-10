import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("logout success auth route contract", () => {
  it("uses the auth layout mode and a reduced success copy", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const pageSource = readFileSync(path.resolve(currentDir, "+page.ts"), "utf8");

    expect(pageSource).toContain("hidePageHeading: true");
    expect(pageSource).toContain("authLayout: true");
    expect(routeSource).toContain('title="Abgemeldet"');
    expect(routeSource).not.toContain("Erfolgreich abgemeldet");
    expect(routeSource).not.toContain("Du wurdest von GUSTAV und dem Anmeldedienst abgemeldet.");
  });
});
