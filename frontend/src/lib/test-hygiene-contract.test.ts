import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("frontend test artifact hygiene", () => {
  it("ignores Playwright runtime artifacts", () => {
    const ignoreFile = readFileSync(path.resolve(process.cwd(), ".gitignore"), "utf8");

    expect(ignoreFile).toMatch(/^test-results\/$/m);
    expect(ignoreFile).toMatch(/^playwright-report\/$/m);
  });
});
