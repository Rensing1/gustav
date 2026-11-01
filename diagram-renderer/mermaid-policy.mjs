/** Shared browser/print policy; diagram definitions cannot supply site settings. */
export function diagramConfig(theme, keys) {
  return {
    layout: "dagre", look: "classic",
    startOnLoad: false, securityLevel: "strict", htmlLabels: false,
    theme: theme === "dark" ? "dark" : "default", darkMode: theme === "dark",
    fontFamily: "DejaVu Sans, sans-serif", maxTextSize: 50_000, maxEdges: 500,
    suppressErrorRendering: true, secure: [...new Set([...keys, "secure"])]
  };
}

export function diagramInputError(source) {
  if (typeof source !== "string") return "invalid_diagram";
  if (source.length > 50_000) return "diagram_too_large";
  // Decode CSS escapes before checking fetch syntax. Ordinary URLs in labels are text.
  const decoded = source.replace(/\\([0-9a-f]{1,6})\s?/gi, (_, hex) => String.fromCodePoint(Math.min(parseInt(hex, 16), 0x10ffff)))
    .replace(/\\([^\n])/g, "$1");
  if (/url\s*\(|@import|@font-face|\b(?:img|image)\s*:/i.test(decoded)) return "invalid_diagram";
  return null;
}
