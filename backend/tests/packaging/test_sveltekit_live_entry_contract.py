"""Contract tests for the SvelteKit live entry pages."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_live_entry_pages() -> None:
    live_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.server.ts"
    live_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.svelte"
    course_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "courses" / "[courseId]" / "+page.server.ts"
    course_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "courses" / "[courseId]" / "+page.svelte"

    for path in (live_loader_path, live_page_path, course_loader_path, course_page_path):
        assert path.is_file(), f"Missing live entry page: {path}"

    assert "/api/teaching/courses" in live_loader_path.read_text(encoding="utf-8")
    assert "/api/teaching/views/courses/" in course_loader_path.read_text(encoding="utf-8")
