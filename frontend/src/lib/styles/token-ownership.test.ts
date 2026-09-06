import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import { describe, expect, it } from "vitest";

const directory = path.dirname(fileURLToPath(import.meta.url));
const tokenName = /^--(?:font|color|radius|space|layout)-/;

describe("product token ownership", () => {
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
