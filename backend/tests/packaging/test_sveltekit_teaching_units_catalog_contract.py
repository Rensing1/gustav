"""Contract tests for the teacher units catalog page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_teacher_units_catalog_page() -> None:
    loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "+page.server.ts"
    page_path = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "+page.svelte"

    assert loader_path.is_file(), f"Missing units catalog loader: {loader_path}"
    assert page_path.is_file(), f"Missing units catalog page: {page_path}"

    loader_src = loader_path.read_text(encoding="utf-8")
    page_src = page_path.read_text(encoding="utf-8")

    assert "/api/teaching/views/units/catalog" in loader_src
    assert "url.searchParams" in loader_src
    assert "breadcrumbs" in loader_src
    assert "hidePageHeading" in loader_src
    assert 'workspaceLayout: "wide"' in loader_src
    assert "wideWorkspaceShell" not in loader_src
    assert "export const actions" in loader_src
    assert "/api/teaching/units" in loader_src

    assert "workspace-units-catalog" in page_src
    assert "TeacherUnitsCatalogToolbar" in page_src
    assert "TeacherUnitsCatalogList" in page_src
    assert "Neue Lerneinheit" in page_src
    assert 'from "$app/navigation"' in page_src
    assert "goto(" in page_src
    assert "setTimeout" in page_src
    assert "workspace-modal-card" in page_src
    assert "workspace-units-preview" not in page_src
