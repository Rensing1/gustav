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

  it("keeps the Safari focus fallback while modern browsers suppress pointer focus rings", () => {
    const source = readFileSync(path.resolve(stylesDir, "ui-primitives.css"), "utf8");
    const root = postcss.parse(source, { from: "ui-primitives.css" });
    const fallbackSelector = ":is(a[href], button, input, select, textarea, summary, [tabindex]):focus";
    const modernSelector = `${fallbackSelector}:not(:focus-visible)`;
    let hasFallback = false;
    let hasModernOverride = false;

    root.walkRules((rule) => {
      const parent = rule.parent;
      if (rule.selector === fallbackSelector && rule.parent === root) {
        hasFallback = rule.some(
          (node) => node.type === "decl" && node.prop === "outline" && node.value.includes("--focus-ring-width")
        );
      }
      if (
        rule.selector === modernSelector
        && parent?.type === "atrule"
        && parent.name === "supports"
        && parent.params === "selector(:focus-visible)"
      ) {
        hasModernOverride = rule.some(
          (node) => node.type === "decl" && node.prop === "outline" && node.value === "none"
        );
      }
    });

    expect(hasFallback).toBe(true);
    expect(hasModernOverride).toBe(true);
  });
});
