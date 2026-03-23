"""Contract tests for the SvelteKit live unit pages."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_live_unit_page() -> None:
    loader_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "live" / "courses" / "[courseId]" / "units" / "[unitId]" / "+page.server.ts"
    )
    page_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "live" / "courses" / "[courseId]" / "units" / "[unitId]" / "+page.svelte"
    )

    assert loader_path.is_file(), f"Missing live unit loader: {loader_path}"
    assert page_path.is_file(), f"Missing live unit page: {page_path}"

    loader_source = loader_path.read_text(encoding="utf-8")
    assert "/api/live/views/courses/" in loader_source
    assert "/matrix" in loader_source
    assert "/detail-sheet" in loader_source
