"""Contract tests for the SvelteKit concern box pages and global navigation."""

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


def test_root_layout_contains_role_aware_concern_box_topbar_link() -> None:
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"
    src = layout_path.read_text(encoding="utf-8")
    account_panel = src.split('<div class="account-menu__panel">', maxsplit=1)[1]

    assert 'function concernBoxHref(): string' in src
    assert '"/learning/kummerkasten"' in src
    assert '"/teaching/kummerkasten"' in src
    assert 'class="app-topbar-concern-link"' in src
    assert 'href={concernBoxHref()}' in src
    assert 'href="/learning/kummerkasten"' not in account_panel
    assert 'href="/teaching/kummerkasten"' not in account_panel
