"""Contract tests for the first SvelteKit diagnostics course matrix page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_diagnostics_course_matrix_page() -> None:
    loader_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "courses" / "[courseId]" / "+page.server.ts"
    )
    page_path = REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "courses" / "[courseId]" / "+page.svelte"

    assert loader_path.is_file(), f"Missing diagnostics matrix loader: {loader_path}"
    assert page_path.is_file(), f"Missing diagnostics matrix page: {page_path}"
    assert "/api/diagnostics/views/courses/" in loader_path.read_text(encoding="utf-8")
    assert "/matrix" in loader_path.read_text(encoding="utf-8")
