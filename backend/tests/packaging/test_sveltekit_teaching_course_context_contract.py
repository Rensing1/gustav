"""Contract tests for the first SvelteKit teacher course context page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_teacher_course_context_page() -> None:
    loader_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "+page.server.ts"
    )
    page_path = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "+page.svelte"

    assert loader_path.is_file(), f"Missing course context loader: {loader_path}"
    assert page_path.is_file(), f"Missing course context page: {page_path}"
    loader_src = loader_path.read_text(encoding="utf-8")
    page_src = page_path.read_text(encoding="utf-8")

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

    assert "workspace-composer-header" in page_src
    assert "workspace-composer-layout" in page_src
    assert "workspace-composer-sidecar" in page_src
    assert "Lerneinheiten" in page_src
    assert "Mitglieder" in page_src
    assert "Kurs" in page_src
    assert "Lerneinheit hinzufügen" in page_src
    assert "workspace-row-menu" in page_src
    assert "workspace-unit-order" in page_src
    assert "workspace-unit-handle" in page_src
    assert "workspace-drawer-card" in page_src
    assert "workspace-overflow-menu" in page_src
    assert "?/saveCourse" in page_src
    assert "?/deleteCourse" in page_src
    assert "?/removeMember" in page_src
    assert "?/removeUnit" in page_src
    assert "?/reorderModules" in page_src
    assert "workspace-modal-card" in page_src
    assert "workspace-tabs" not in page_src
    assert "workspace-disclosure" not in page_src
    assert "Position {unit.position}" not in page_src
