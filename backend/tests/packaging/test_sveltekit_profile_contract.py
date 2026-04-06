"""Contract tests for the SvelteKit profile page and account menu link."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_profile_page() -> None:
    loader = REPO_ROOT / "frontend" / "src" / "routes" / "profile" / "+page.server.ts"
    page = REPO_ROOT / "frontend" / "src" / "routes" / "profile" / "+page.svelte"

    assert loader.is_file(), f"Missing profile loader: {loader}"
    assert page.is_file(), f"Missing profile page: {page}"
    assert "/api/app/profile" in loader.read_text(encoding="utf-8")


def test_root_layout_contains_profile_account_link() -> None:
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"
    src = layout_path.read_text(encoding="utf-8")

    assert 'href="/profile"' in src
