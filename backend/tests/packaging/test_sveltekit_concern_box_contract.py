"""Contract tests for the SvelteKit concern box pages and account menu links."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_concern_box_pages() -> None:
    learner_loader = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "kummerkasten" / "+page.server.ts"
    learner_page = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "kummerkasten" / "+page.svelte"
    teacher_loader = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "kummerkasten" / "+page.server.ts"
    teacher_page = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "kummerkasten" / "+page.svelte"

    for path in (learner_loader, learner_page, teacher_loader, teacher_page):
        assert path.is_file(), f"Missing concern box page: {path}"

    assert "/api/learning/views/concern-box" in learner_loader.read_text(encoding="utf-8")
    assert "/api/teaching/views/concern-box" in teacher_loader.read_text(encoding="utf-8")


def test_root_layout_contains_concern_box_account_links() -> None:
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"
    src = layout_path.read_text(encoding="utf-8")

    assert 'href="/learning/kummerkasten"' in src
    assert 'href="/teaching/kummerkasten"' in src
