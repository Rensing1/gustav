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

  it("sends createMaterial forms with multipart encoding for file uploads", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('action="?/createMaterial"');
    expect(routeSource).toContain('enctype="multipart/form-data"');
    expect(routeSource).toContain('<input name="upload_file" type="file" onchange={handleCreateMaterialFileChange} />');
    expect(routeSource).toContain('<input name="intent_id" type="hidden" value=');
    expect(routeSource).toContain('<input name="sha256" type="hidden" value=');
  });

  it("renders an inline success status for editor actions", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("editorMessage");
    expect(routeSource).toContain("workspace-note workspace-note--success");
  });
});
