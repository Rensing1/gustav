import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("register auth route contract", () => {
  it("redirects directly without collecting the email twice", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(serverSource).toContain("/auth/register?redirect=");
    expect(routeSource).not.toContain("<form");
    expect(routeSource).not.toContain("<input");
  });
});
