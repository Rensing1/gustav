import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const pageSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");
const stylesSource = readFileSync(path.resolve(currentDir, "../../../../lib/styles/teaching-workspace.css"), "utf8");
const appStylesSource = readFileSync(path.resolve(currentDir, "../../../../lib/styles/app.css"), "utf8");

describe("teacher course workspace contract", () => {
  it("uses the wide shared heading and one flat course workspace", () => {
    expect(serverSource).toContain("wideWorkspaceShell: true");
    expect(pageSource).toContain('PageActionHead');
    expect(pageSource).toContain('TeacherCourseUnitList');
    expect(pageSource).toContain('teacher-course-workspace');
    expect(pageSource).not.toContain('workspace-composer-layout');
    expect(pageSource).not.toContain('workspace-panel');
    expect(pageSource).not.toContain('memberPreview');
    expect(pageSource).not.toContain('Nicht gesetzt');
    expect(pageSource).not.toContain('Diagnostik öffnen');
    expect(serverSource).toContain('breadcrumbs: [] as BreadcrumbItem[]');
  });

  it("keeps course-detail styles in the teaching layer and responsive", () => {
    expect(stylesSource).toContain('.teacher-course-workspace {');
    expect(stylesSource).toContain('width: min(100%, var(--layout-content-max));');
    expect(stylesSource).toContain('@media (max-width: 48rem)');
    expect(appStylesSource).not.toContain('.workspace-page--course-context');
    expect(appStylesSource).not.toContain('.workspace-composer-layout');
  });

  it("loads deletion impact through the course drawer query and preserves reorder drafts", () => {
    expect(pageSource).toContain('pageHref({ course: "1" })');
    expect(serverSource).toContain('moduleIds');
    expect(pageSource).not.toContain('href={`/teaching/courses/${data.course.id}/members`}');
  });

  it("uses the shared accessible drawer instead of duplicating its shell", () => {
    expect(pageSource.match(/<WorkspaceDrawer/g)).toHaveLength(2);
    expect(pageSource).not.toContain('workspace-modal--drawer');
    expect(pageSource).not.toContain('aria-label="Drawer schließen"');
    expect(pageSource).toContain('removeDrawerQuery("course")');
    expect(pageSource).toContain('removeDrawerQuery("members", "add-member", "member-q")');
  });
});
