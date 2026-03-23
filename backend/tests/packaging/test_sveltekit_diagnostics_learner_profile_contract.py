"""Contract tests for the SvelteKit diagnostics learner profile page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_diagnostics_learner_profile_page() -> None:
    loader_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "learners" / "[studentSub]" / "+page.server.ts"
    )
    page_path = REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "learners" / "[studentSub]" / "+page.svelte"

    assert loader_path.is_file(), f"Missing diagnostics learner profile loader: {loader_path}"
    assert page_path.is_file(), f"Missing diagnostics learner profile page: {page_path}"
    assert "/api/diagnostics/views/learners/" in loader_path.read_text(encoding="utf-8")
    assert "/profile" in loader_path.read_text(encoding="utf-8")
