import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import postcss from "postcss";

const stylesDir = path.resolve(process.cwd(), "src/lib/styles");

describe("global CSS syntax", () => {
  it("parses every shipped stylesheet without recovery warnings", () => {
    const styleFiles = [
      "theme-tokens.css",
      "typography.css",
      "app.css",
      "ui-primitives.css",
      "learning-unit.css",
      "teaching-workspace.css",
      "auth-theme.css"
    ];

    for (const fileName of styleFiles) {
      const source = readFileSync(path.resolve(stylesDir, fileName), "utf8");
      expect(() => postcss.parse(source, { from: fileName })).not.toThrow();
    }
  });
});
