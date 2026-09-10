import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import { describe, expect, it } from "vitest";

const directory = path.dirname(fileURLToPath(import.meta.url));
const tokenName = /^--(?:font|color|radius|space|layout)-/;

describe("product token ownership", () => {
  it("themes the actual H5P tutorial and example text spans", () => {
    const h5p = postcss.parse(readFileSync(path.resolve(directory, "../../../../h5p-service/vendor/theme/h5p-gustav.css"), "utf8"));
    for (const selector of [".h5p-tutorial-url-label", ".h5p-example-url-label"]) {
      const colors: string[] = [];
      h5p.walkRules((rule) => {
        if (rule.selectors.includes(selector)) rule.walkDecls("color", (declaration) => { colors.push(declaration.value); });
      });
      expect(colors).toContain("var(--color-link)");
    }
  });
  it("resolves every H5P theme variable from the canonical tokens", () => {
    const tokens = readFileSync(path.join(directory, "theme-tokens.css"), "utf8");
    const h5p = readFileSync(path.resolve(directory, "../../../../h5p-service/vendor/theme/h5p-gustav.css"), "utf8");
    const definitions = new Set([...tokens.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((match) => match[1]));
    const references = [...h5p.matchAll(/var\((--[a-z0-9-]+)/g)].map((match) => match[1]);
    expect([...new Set(references.filter((name) => !definitions.has(name)))]).toEqual([]);
  });
  it("defines design tokens only in theme-tokens.css and resolves every reference", () => {
    const definitions = new Set<string>();
    const references: { file: string; token: string }[] = [];
    const foreignDefinitions: string[] = [];
    for (const file of readdirSync(directory, { recursive: true }).filter((name) => String(name).endsWith(".css"))) {
      const name = String(file);
      const root = postcss.parse(readFileSync(path.join(directory, name), "utf8"));
      root.walkDecls((declaration) => {
        if (tokenName.test(declaration.prop)) {
          definitions.add(declaration.prop);
          if (name !== "theme-tokens.css") foreignDefinitions.push(`${name}: ${declaration.prop}`);
        }
        for (const reference of declaration.value.matchAll(/var\((--[a-z0-9-]+)/g)) {
          if (tokenName.test(reference[1])) references.push({ file: name, token: reference[1] });
        }
      });
    }
    expect(foreignDefinitions).toEqual([]);
    expect(references.filter(({ token }) => !definitions.has(token))).toEqual([]);
  });
});
