import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher home design contract", () => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const css = readFileSync(path.resolve(currentDir, "../../styles/teaching-workspace.css"), "utf8");
  const launcher = readFileSync(path.resolve(currentDir, "TeacherLiveLauncher.svelte"), "utf8");
  const page = readFileSync(path.resolve(currentDir, "../../../routes/teaching/+page.svelte"), "utf8");

  it("keeps the work starter flat, token based and responsive", () => {
    expect(css).toMatch(/\.teacher-home-workstarter__grid\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/s);
    expect(css).toMatch(/\.teacher-home-workstarter__section\s*\+\s*\.teacher-home-workstarter__section\s*\{[^}]*border-inline-start:/s);
    expect(css).toContain("@media (max-width: 64rem)");
    expect(css).toMatch(/@media \(max-width: 64rem\)[\s\S]*\.teacher-home-workstarter__grid\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    expect(css).toMatch(/@media \(max-width: 64rem\)[\s\S]*\.teacher-home-workstarter__section\s*\+\s*\.teacher-home-workstarter__section\s*\{[^}]*border-block-start:/s);
    expect(css).not.toMatch(/\.teacher-home-[^{]*\{[^}]*(?:#[0-9a-f]{3,8}|rgba?\()/i);
  });

  it("keeps productive teacher home styles out of Svelte components", () => {
    expect(launcher).not.toContain("<style");
    expect(page).not.toContain("<style");
  });
});
