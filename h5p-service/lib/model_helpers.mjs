export const H5P_THEME_STYLESHEET_PATH = "/h5p/theme/h5p-gustav.css";


export function ensureThemeStylesLast(styles) {
  const arr = Array.isArray(styles) ? styles.filter((style) => style !== H5P_THEME_STYLESHEET_PATH) : [];
  arr.push(H5P_THEME_STYLESHEET_PATH);
  return arr;
}


export function ensureDivEmbedTypes(embedTypes) {
  // Lumi's `<h5p-player>` prefers DIV when possible (less iframes, better theming).
  // Some packages advertise iframe only, so GUSTAV adds div support for the
  // embedded player model while preserving the package's remaining embed types.
  const raw = Array.isArray(embedTypes) ? embedTypes : [];
  const out = ["div"];
  for (const embedType of raw) {
    if (!embedType) continue;
    if (embedType === "div") continue;
    if (out.includes(embedType)) continue;
    out.push(embedType);
  }
  return out;
}
