import { readFileSync } from "node:fs";
import path from "node:path";

const globalStyleFiles = [
  "app.css",
  "learning-unit.css",
  "teaching-workspace.css",
  "auth-theme.css",
  "design-system.css"
];
const workspaceStyleFiles = ["app.css", "learning-unit.css"];

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
