import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const packageRoot = path.dirname(require.resolve("@lumieducation/h5p-server/package.json"));
const dictionaries = new Map();

// Use the translations shipped with the locked runtime, not a second manually
// maintained vocabulary. Only fixed language/namespace paths are read at start.
for (const language of ["de", "en"]) {
  const entries = new Map();
  for (const namespace of ["client", "metadata-semantics", "copyright-semantics"]) {
    const values = JSON.parse(readFileSync(path.join(packageRoot, "build/assets/translations", namespace, `${language}.json`), "utf8"));
    const flatten = (value, prefix) => {
      if (typeof value === "string") entries.set(prefix, value);
      else for (const [key, child] of Object.entries(value)) flatten(child, `${prefix}.${key}`);
    };
    for (const [key, value] of Object.entries(values)) flatten(value, `${namespace}:${key}`);
  }
  dictionaries.set(language, entries);
}

/** Public H5P translation callback; unknown keys retain H5P's own fallback. */
export function translateH5p(key, language) {
  return dictionaries.get(language === "en" ? "en" : "de").get(key)
    ?? dictionaries.get("en").get(key)
    ?? key;
}
