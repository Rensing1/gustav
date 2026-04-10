import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher node editor contract", () => {
  it("uses shared page and node-editor components", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const appCss = readFileSync(path.resolve(currentDir, "../../../../../../lib/styles/app.css"), "utf8");

    expect(routeSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(routeSource).toContain(
      'import TeacherNodeEditorProperties from "$lib/components/teacher-node-editor/TeacherNodeEditorProperties.svelte";'
    );
    expect(routeSource).toContain(
      'import TeacherNodeEditorSection from "$lib/components/teacher-node-editor/TeacherNodeEditorSection.svelte";'
    );
    expect(routeSource).toContain("<PageActionHead");
    expect(routeSource).toContain("<TeacherNodeEditorProperties");
    expect(routeSource).toContain("<TeacherNodeEditorSection");
    expect(appCss).not.toContain(".workspace-field {");
    expect(appCss).not.toContain(".workspace-button {");
  });
});
