import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const pageSource = readFileSync(path.resolve(currentDir, "../../routes/teaching/units/[unitId]/nodes/[nodeId]/+page.svelte"), "utf8");
const cssSource = readFileSync(path.resolve(currentDir, "../styles/teaching-workspace.css"), "utf8");
const sectionSource = readFileSync(
  path.resolve(currentDir, "../components/teacher-node-editor/TeacherNodeEditorSection.svelte"),
  "utf8"
);

describe("module editor design contract", () => {
  it("keeps all productive workbench styles in the teaching layer", () => {
    expect(pageSource).not.toContain("<style");
    expect(cssSource).toContain(".teacher-module-workbench");
    expect(cssSource).toContain("container-type: inline-size");
  });

  it("switches from two flat areas to full-width stages at the component boundary", () => {
    expect(cssSource).toMatch(/@container\s+\(max-width:\s*63\.99rem\)/);
    expect(cssSource).toContain('[data-module-stage="contents"]');
    expect(cssSource).toContain('[data-module-stage="editor"]');
  });

  it("uses the wide workspace while keeping the editing measure readable", () => {
    expect(cssSource).toMatch(
      /\.teacher-module-workbench\.workspace-node-editor--content-only\s*\{[^}]*max-width:\s*none;[^}]*width:\s*100%;/s
    );
    expect(cssSource).toMatch(
      /\.teacher-module-workbench\s*\{[^}]*grid-template-columns:\s*clamp\(22rem,\s*23cqw,\s*25rem\)\s+minmax\(0,\s*1fr\);/s
    );
    expect(cssSource).toMatch(
      /\.teacher-module-editor-pane__content\s*\{[^}]*width:\s*min\(100%,\s*72rem\);[^}]*margin-inline:\s*auto;/s
    );
    expect(cssSource).toMatch(
      /\.teacher-module-outline\s*\{[^}]*position:\s*sticky;[^}]*top:/s
    );
    expect(cssSource).toMatch(
      /\.workspace-node-editor-card\.workspace-node-editor-card--workbench\s*\{[^}]*border:\s*0;[^}]*box-shadow:\s*none;/s
    );
    expect(cssSource).toMatch(
      /\.teacher-node-editor-section--workbench\s+\.teacher-node-editor-section__create\s*\{[^}]*border:\s*0;/s
    );
  });

  it("places content actions in the editor section heading", () => {
    expect(sectionSource).toContain("actions?: Snippet");
    expect(sectionSource).toContain("teacher-node-editor-section__actions");
    expect(sectionSource).toContain("{@render actions()}");
    expect(pageSource).toContain("actions={selectedMaterial ? materialActions : undefined}");
    expect(pageSource).toContain("actions={selectedTask ? taskActions : undefined}");
  });

  it("keeps material and task groups separate and provides keyboard reorder actions", () => {
    expect(pageSource).toContain('id="module-materials-heading"');
    expect(pageSource).toContain('id="module-tasks-heading"');
    expect(pageSource).toContain("Nach oben");
    expect(pageSource).toContain("Nach unten");
  });
});
