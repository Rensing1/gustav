import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const pageSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");
const unitsPageSource = readFileSync(path.resolve(currentDir, "../units/+page.svelte"), "utf8");
const stylesSource = readFileSync(path.resolve(currentDir, "../../../lib/styles/teaching-workspace.css"), "utf8");

describe("teacher course catalog contract", () => {
  it("uses the shared heading and a flat lifecycle catalog", () => {
    expect(pageSource).toContain('PageActionHead');
    expect(pageSource).toContain('Aktiv');
    expect(pageSource).toContain('Archiv');
    expect(pageSource).toContain('workspace-course-catalog__row');
    expect(pageSource).not.toContain('workspace-link-card--course');
    expect(serverSource).not.toContain("headerAction:");
  });

  it("requires structured metadata for new courses", () => {
    expect(pageSource).toContain('name="school_year_start"');
    expect(pageSource).toContain('name="subject"');
    expect(pageSource).toContain('name="grade_level"');
    expect(serverSource).toContain('school_year_start: schoolYearStart');
  });

  it("offers batch archiving and restoration without direct deletion", () => {
    expect(serverSource).toContain('archiveSelected');
    expect(serverSource).toContain('restoreCourse');
    expect(serverSource).not.toContain('method: "DELETE"');
  });

  it("uses named actions consistently so catalog actions remain executable", () => {
    expect(serverSource).toContain("createCourse: async");
    expect(serverSource).not.toContain("default: async");
    expect(pageSource).toContain('action="?/createCourse"');
    expect(pageSource).toContain('action="?/archiveSelected"');
  });

  it("shares width, table rhythm and responsive catalog rules with units", () => {
    expect(serverSource).toContain("wideWorkspaceShell: true");
    expect(pageSource).toContain("teacher-catalog");
    expect(unitsPageSource).toContain("teacher-catalog");
    expect(pageSource).toContain("teacher-catalog__columns");
    expect(stylesSource).toContain(".teacher-catalog {");
    expect(stylesSource).toContain("width: min(100%, var(--layout-content-max));");
    expect(stylesSource).toContain("grid-template-columns: var(--teacher-catalog-columns);");
    expect(stylesSource).toContain("@media (max-width: 48rem)");
  });
});
