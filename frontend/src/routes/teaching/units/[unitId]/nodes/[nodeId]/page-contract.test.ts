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
    expect(routeSource).toContain('name="upload_file"');
    expect(routeSource).toContain('onchange={handleCreateMaterialFileChange}');
    expect(routeSource).toContain('onsubmitcapture={handleCreateMaterialSubmit}');
    expect(routeSource).not.toContain('onsubmit={handleCreateMaterialSubmit}');
    expect(routeSource).toContain("event.stopImmediatePropagation();");
    expect(routeSource).toContain('<input name="intent_id" type="hidden" value=');
    expect(routeSource).toContain('<input name="sha256" type="hidden" value=');
  });

  it("offers self-contained simulations with an explicit sandboxed preview", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('<option value="simulation">Interaktive Simulation</option>');
    expect(routeSource).toContain('accept=".html,text/html"');
    expect(routeSource).toContain("Vorschau starten");
    expect(routeSource).toContain('sandbox="allow-scripts"');
    expect(routeSource).toContain('referrerpolicy="no-referrer"');
  });

  it("renders accessible inline status messages for editor actions", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("editorMessage");
    expect(routeSource).toContain("<StatusMessage");
    expect(routeSource).toContain("tone={editorMessage.tone}");
    expect(routeSource).toContain("title={editorMessage.text}");
  });

  it("keeps create actions available in the compact content stage without duplicating them on desktop", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const teachingCss = readFileSync(
      path.resolve(currentDir, "../../../../../../lib/styles/teaching-workspace.css"),
      "utf8"
    );

    expect(routeSource).toContain("teacher-module-outline__compact-add");
    expect(teachingCss).toMatch(/\.teacher-module-outline__compact-add\s*\{[^}]*display:\s*none/s);
    expect(teachingCss).toMatch(
      /@container \(max-width: 63\.99rem\)[\s\S]*\.teacher-module-outline__compact-add\s*\{[^}]*display:\s*inline-grid/s
    );
  });

  it("returns to a selected module without opening its properties automatically", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain("?module=${encodeURIComponent(editorState.node.id)}");
    expect(routeSource).not.toContain("&quick=1");
  });
});
