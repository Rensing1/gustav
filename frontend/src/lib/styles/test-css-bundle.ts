import { readFileSync } from "node:fs";
import path from "node:path";

const globalStyleFiles = [
  "theme-tokens.css",
  "typography.css",
  "app.css",
  "ui-primitives.css",
  "learning-unit.css",
  "teaching-workspace.css",
  "auth-theme.css"
];
const workspaceStyleFiles = [
  "theme-tokens.css",
  "typography.css",
  "app.css",
  "ui-primitives.css",
  "learning-unit.css"
];

export function readGlobalCssBundle(stylesDir: string): string {
  return globalStyleFiles
    .map((fileName) => readFileSync(path.resolve(stylesDir, fileName), "utf8"))
    .join("\n");
}

export function readWorkspaceCssBundle(stylesDir: string): string {
  return workspaceStyleFiles
    .map((fileName) => readFileSync(path.resolve(stylesDir, fileName), "utf8"))
    .join("\n");
}
