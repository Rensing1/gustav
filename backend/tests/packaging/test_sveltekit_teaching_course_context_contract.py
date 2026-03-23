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
    assert "/api/teaching/views/courses/" in loader_path.read_text(encoding="utf-8")
    assert "/context" in loader_path.read_text(encoding="utf-8")
