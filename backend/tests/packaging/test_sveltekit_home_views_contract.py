"""Contract tests for the first SvelteKit room pages."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_home_room_pages() -> None:
    learner_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "+page.server.ts"
    learner_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "+page.svelte"
    teacher_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "+page.server.ts"
    teacher_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "+page.svelte"

    for path in (learner_loader_path, learner_page_path, teacher_loader_path, teacher_page_path):
        assert path.is_file(), f"Missing home view page: {path}"

    assert "/api/learning/views/learner-home" in learner_loader_path.read_text(encoding="utf-8")
    assert "/api/teaching/views/teacher-home" in teacher_loader_path.read_text(encoding="utf-8")
