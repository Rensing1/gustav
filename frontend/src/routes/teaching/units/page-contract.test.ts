import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("teacher units catalog route contract", () => {
  it("uses the shared page head and a flat catalog table without the old filter contract", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(routeSource).toContain('import PageActionHead from "$lib/components/ui/PageActionHead.svelte";');
    expect(routeSource).toContain(
      'import TeacherUnitsCatalogToolbar from "$lib/components/teacher-units-catalog/TeacherUnitsCatalogToolbar.svelte";'
    );
    expect(routeSource).toContain(
      'import TeacherUnitsCatalogList from "$lib/components/teacher-units-catalog/TeacherUnitsCatalogList.svelte";'
    );
    expect(routeSource).toContain("<PageActionHead");
    expect(routeSource).toContain("<TeacherUnitsCatalogToolbar");
    expect(routeSource).toContain("<TeacherUnitsCatalogList");
    expect(routeSource).toContain('class="workspace-modal"');
    expect(routeSource).not.toContain("activeViewLabel=");
    expect(routeSource).not.toContain("data.catalog.views");
    expect(routeSource).not.toContain("data.catalog.filters");
    expect(routeSource).not.toContain('href={data.catalog.create_href}');
    expect(routeSource).not.toContain("data.showCreateDialog");
    expect(routeSource).not.toContain("workspace-section workspace-units-catalog__workspace");
    expect(routeSource).not.toContain("Status</span>");
    expect(serverSource).toContain("hidePageHeading: true");
    expect(serverSource).toContain("wideWorkspaceShell: true");
    expect(serverSource).not.toContain("headerAction:");
    expect(serverSource).not.toContain("showCreateDialog:");
  });
});
