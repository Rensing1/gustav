import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import postcss from "postcss";

/**
 * Return every cascade-layer rule found in a CSS source.
 *
 * The production bundle must not expose `@layer` to older WebKit versions:
 * they discard the complete rule block instead of applying its contents.
 */
export function findCascadeLayers(css, from = "generated.css") {
  const root = postcss.parse(css, { from });
  const layers = [];

  root.walkAtRules((rule) => {
    if (rule.name.toLowerCase() === "layer") {
      layers.push(rule.params.trim() || "<anonymous>");
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
 * Reject a generated client bundle that still contains cascade layers.
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
