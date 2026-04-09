import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("root page server contract", () => {
  it("reuses the parent bootstrap instead of fetching session bootstrap again", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain("parent()");
    expect(serverSource).not.toContain('"/api/app/session-bootstrap"');
    expect(serverSource).not.toContain("readTypedJsonOrNull");
  });
});
