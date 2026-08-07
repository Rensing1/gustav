"""Contract tests for the first SvelteKit teacher course context page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_teacher_course_context_page() -> None:
    loader_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "+page.server.ts"
    )
    page_path = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "+page.svelte"
    unit_list_path = (
        REPO_ROOT / "frontend" / "src" / "lib" / "components" / "teacher-course" / "TeacherCourseUnitList.svelte"
    )
    drawer_path = REPO_ROOT / "frontend" / "src" / "lib" / "components" / "ui" / "WorkspaceDrawer.svelte"

    assert loader_path.is_file(), f"Missing course context loader: {loader_path}"
    assert page_path.is_file(), f"Missing course context page: {page_path}"
    assert unit_list_path.is_file(), f"Missing course unit list: {unit_list_path}"
    assert drawer_path.is_file(), f"Missing shared workspace drawer: {drawer_path}"
    loader_src = loader_path.read_text(encoding="utf-8")
    page_src = page_path.read_text(encoding="utf-8")
    unit_list_src = unit_list_path.read_text(encoding="utf-8")
    drawer_src = drawer_path.read_text(encoding="utf-8")

    assert "/api/teaching/courses/" in loader_src
    assert "/api/teaching/courses/" in loader_src
    assert "/api/teaching/courses/" in loader_src
    assert "/api/teaching/courses/" in loader_src
    assert "/members?limit=200&offset=0" in loader_src
    assert "/modules" in loader_src
    assert "/api/teaching/units?limit=100&offset=0" in loader_src
    assert "/api/users/search" in loader_src
    assert "export const actions" in loader_src
    assert "/members/" in loader_src
    assert "/modules/reorder" in loader_src
    assert "showAddMemberDialog" in loader_src
    assert "showAddUnitDialog" in loader_src
    assert "showCourseDrawer" in loader_src
    assert "showMembersDrawer" in loader_src
    assert "hidePageHeading" in loader_src

    assert "PageActionHead" in page_src
    assert "TeacherCourseUnitList" in page_src
    assert "teacher-course-workspace" in page_src
    assert "teacher-course-workspace__section" in page_src
    assert "teacher-course-workspace__management-row" in page_src
    assert "Lerneinheiten" in page_src
    assert "Mitglieder" in page_src
    assert "Kurseinstellungen" in page_src
    assert "Lerneinheit hinzufügen" in page_src
    assert "WorkspaceDrawer" in page_src
    assert "workspace-drawer-card" in drawer_src
    assert 'event.key !== "Escape"' in drawer_src
    assert 'aria-label="Seitenleiste schließen"' in drawer_src
    assert "?/saveCourse" in page_src
    assert "?/deleteCourse" in page_src
    assert "?/removeMember" in page_src
    assert "?/removeUnit" in unit_list_src
    assert "?/reorderModules" in unit_list_src
    assert "workspace-row-menu" in unit_list_src
    assert "workspace-modal-card" in page_src
    assert "workspace-tabs" not in page_src
    assert "workspace-disclosure" not in page_src
    assert "workspace-composer-layout" not in page_src
    assert "Diagnostik öffnen" not in page_src
    assert "Position {unit.position}" not in page_src
