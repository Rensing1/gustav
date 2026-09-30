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
  // CSS comments may separate tokens wherever whitespace is allowed.
  const skipTrivia = () => {
    while (cursor < params.length) {
      if (/\s/.test(params[cursor])) {
        cursor += 1;
      } else if (params.startsWith("/*", cursor)) {
        const commentEnd = params.indexOf("*/", cursor + 2);
        cursor = commentEnd === -1 ? params.length : commentEnd + 2;
      } else {
        return;
      }
    }
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

  skipTrivia();
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

  skipTrivia();
  const remainder = params.slice(cursor);
  const namedLayer = /^layer\(\s*([^)]*?)\s*\)/i.exec(remainder);
  if (namedLayer) return namedLayer[1]?.trim() || "<anonymous import>";

  const anonymousLayer = /^layer(?=\s|\/\*|$)/i.exec(remainder);
  return anonymousLayer ? "<anonymous import>" : null;
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

/** Check only the agreed contracts: graph strokes, dialog tokens and viewport sizes. */
export function findMissingBrowserFallbacks(css, from = "generated.css") {
  const root = postcss.parse(css, { from });
  const findings = [];
  root.walkDecls((declaration) => {
    const viewport = /\b\d*\.?\d+(?:dvh|svh)\b/.test(declaration.value);
    const color = declaration.value.includes("color-mix(") && (declaration.prop === "stroke" || declaration.prop.startsWith("--dialog-"));
    if (!viewport && !color) return;
    // Values containing var() are checked only at computed-value time. Without
    // a supports guard they can discard the compatible declaration too.
    let parent = declaration.parent;
    while (parent) {
      if (parent.type === "atrule" && parent.name === "supports" && (
        (color && /^\(color:\s*color-mix\(/.test(parent.params)) || (viewport && /^\(height:\s*100(?:dvh|svh)\)/.test(parent.params))
      )) return;
      parent = parent.parent;
    }
    const previous = declaration.parent.nodes.slice(0, declaration.parent.nodes.indexOf(declaration));
    if (declaration.value.includes("var(") || color && declaration.prop.startsWith("--")) {
      findings.push(declaration.prop);
    } else if (!previous.some((item) => item.type === "decl" && item.prop === declaration.prop && !/color-mix\(|\b\d*\.?\d+(?:dvh|svh)\b/.test(item.value))) {
      findings.push(declaration.prop);
    }
  });
  return findings;
}

/**
 * Reject cascade layers and missing agreed browser fallbacks in client CSS.
 *
 * Parameters:
 * - `directory`: Vite's generated client-asset directory.
 *
 * Expected behavior:
 * - Resolves silently when all generated CSS is compatible.
 * - Throws with relative file names and violated contracts when rules remain.
 *
 * Permissions:
 * - The caller only needs read access to the generated build directory.
 */
export async function assertBrowserCompatibleCss(directory) {
  const findings = [];

  for (const file of await listCssFiles(directory)) {
    const css = await readFile(file, "utf8");
    const layers = findCascadeLayers(css, file);
    if (layers.length > 0) {
      findings.push(`${path.relative(directory, file)}: ${layers.join(", ")}`);
    }
    const missing = findMissingBrowserFallbacks(css, file);
    if (missing.length) findings.push(`${path.relative(directory, file)}: missing fallback for ${missing.join(", ")}`);
  }

  if (findings.length > 0) {
    throw new Error(
      `Generated CSS violates the iPadOS 15.3 compatibility contracts:\n${findings.join("\n")}`
    );
  }
}
