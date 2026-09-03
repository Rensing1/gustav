import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import postcss from "postcss";

/**
 * Read the optional layer modifier immediately following an `@import` source.
 *
 * `params` is the PostCSS-normalized import parameter string. The function
 * returns the layer name, an anonymous-layer marker, or `null` for a normal
 * import. It is a pure parser and requires no file-system permissions.
 */
function findImportedLayer(params) {
  let cursor = 0;
  const skipWhitespace = () => {
    while (/\s/.test(params[cursor] ?? "")) cursor += 1;
  };
  const consumeString = (quote) => {
    cursor += 1;
    while (cursor < params.length) {
      if (params[cursor] === "\\") {
        cursor += 2;
      } else if (params[cursor] === quote) {
        cursor += 1;
        return;
      } else {
        cursor += 1;
      }
    }
  };

  skipWhitespace();
  if (params[cursor] === '"' || params[cursor] === "'") {
    consumeString(params[cursor]);
  } else if (params.slice(cursor, cursor + 4).toLowerCase() === "url(") {
    cursor += 4;
    let depth = 1;
    while (cursor < params.length && depth > 0) {
      if (params[cursor] === '"' || params[cursor] === "'") {
        consumeString(params[cursor]);
      } else if (params[cursor] === "\\") {
        cursor += 2;
      } else {
        if (params[cursor] === "(") depth += 1;
        if (params[cursor] === ")") depth -= 1;
        cursor += 1;
      }
    }
  } else {
    return null;
  }

  skipWhitespace();
  const match = /^layer(?:\(\s*([^)]*?)\s*\))?(?=\s|$)/i.exec(params.slice(cursor));
  if (!match) return null;
  return match[1]?.trim() || "<anonymous import>";
}

/**
 * Return every cascade-layer use found in a CSS source.
 *
 * The production bundle must not expose `@layer` rules or layer-qualified
 * imports to older WebKit versions: unsupported rules are discarded entirely.
 */
export function findCascadeLayers(css, from = "generated.css") {
  const root = postcss.parse(css, { from });
  const layers = [];

  root.walkAtRules((rule) => {
    if (rule.name.toLowerCase() === "layer") {
      layers.push(rule.params.trim() || "<anonymous>");
    } else if (rule.name.toLowerCase() === "import") {
      const importedLayer = findImportedLayer(rule.params);
      if (importedLayer) layers.push(importedLayer);
    }
  });

  return layers;
}

async function listCssFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listCssFiles(resolved));
    } else if (entry.isFile() && entry.name.endsWith(".css")) {
      files.push(resolved);
    }
  }

  return files.sort();
}

/**
 * Reject a generated client bundle that still uses cascade layers.
 *
 * Parameters:
 * - `directory`: Vite's generated client-asset directory.
 *
 * Expected behavior:
 * - Resolves silently when all generated CSS is compatible.
 * - Throws with relative file names and layer names when incompatible rules remain.
 *
 * Permissions:
 * - The caller only needs read access to the generated build directory.
 */
export async function assertNoCascadeLayers(directory) {
  const findings = [];

  for (const file of await listCssFiles(directory)) {
    const css = await readFile(file, "utf8");
    const layers = findCascadeLayers(css, file);
    if (layers.length > 0) {
      findings.push(`${path.relative(directory, file)}: ${layers.join(", ")}`);
    }
  }

  if (findings.length > 0) {
    throw new Error(
      `Generated CSS still contains cascade layers unsupported by iPadOS 15.3:\n${findings.join("\n")}`
    );
  }
}
