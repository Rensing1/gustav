import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher units catalog route contract", () => {
  function routeSource(fileName: string): string {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    return readFileSync(path.resolve(currentDir, fileName), "utf8");
  }

  it("uses the shared page head and a flat catalog table without the old filter contract", () => {
    const pageSource = routeSource("+page.svelte");
    const serverSource = routeSource("+page.server.ts");

    expect(pageSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(pageSource).toContain(
      'import TeacherUnitsCatalogToolbar from "$lib/components/teacher-units-catalog/TeacherUnitsCatalogToolbar.svelte";'
    );
    expect(pageSource).toContain(
      'import TeacherUnitsCatalogList from "$lib/components/teacher-units-catalog/TeacherUnitsCatalogList.svelte";'
    );
    expect(pageSource).toContain("<PageActionHead");
    expect(pageSource).toContain("<TeacherUnitsCatalogToolbar");
    expect(pageSource).toContain("<TeacherUnitsCatalogList");
    expect(pageSource).toContain('class="workspace-modal"');
    expect(pageSource).not.toContain("activeViewLabel=");
    expect(pageSource).not.toContain("data.catalog.views");
    expect(pageSource).not.toContain("data.catalog.filters");
    expect(pageSource).not.toContain('href={data.catalog.create_href}');
    expect(pageSource).not.toContain("data.showCreateDialog");
    expect(pageSource).not.toContain("workspace-section workspace-units-catalog__workspace");
    expect(pageSource).not.toContain("Status</span>");
    expect(serverSource).toContain("hidePageHeading: true");
    expect(serverSource).toContain("wideWorkspaceShell: true");
    expect(serverSource).not.toContain("headerAction:");
    expect(serverSource).not.toContain("showCreateDialog:");
  });

  it("keeps delete entry points in the catalog while routing deletion to the unit workspace", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const rowSource = readFileSync(
      path.resolve(currentDir, "../../../lib/components/teacher-units-catalog/TeacherUnitsCatalogRow.svelte"),
      "utf8"
    );

    expect(rowSource).toContain('href={`${unit.href}?delete=1`}');
    expect(rowSource).toContain(">Löschen<");
    expect(rowSource).not.toContain('action="?/deleteUnit"');
  });

  it("lets teachers choose the unit type and forwards it to the backend", () => {
    const pageSource = routeSource("+page.svelte");
    const serverSource = routeSource("+page.server.ts");

    expect(pageSource).toContain('name="unit_type"');
    expect(pageSource).toContain('value="modular"');
    expect(pageSource).toContain('value="linear"');
    expect(serverSource).toContain('const unitType = String(form.get("unit_type") || "modular").trim();');
    expect(serverSource).toContain('values: { title, summary, unit_type: unitType }');
    expect(serverSource).toContain("unit_type: unitType");
  });
});
