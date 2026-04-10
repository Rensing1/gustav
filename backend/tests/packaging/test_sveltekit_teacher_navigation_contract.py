"""Contract tests for SvelteKit teacher navigation pages."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_teacher_collection_pages() -> None:
    courses_loader = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.server.ts"
    courses_page = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.svelte"
    units_loader = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "+page.server.ts"
    units_page = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "+page.svelte"

    for path in (courses_loader, courses_page, units_loader, units_page):
        assert path.is_file(), f"Missing teacher navigation page: {path}"

    assert "/api/teaching/courses" in courses_loader.read_text(encoding="utf-8")
    assert "/api/teaching/units" in units_loader.read_text(encoding="utf-8")


def test_frontend_contains_teacher_unit_detail_and_members_pages() -> None:
    unit_loader = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "[unitId]" / "+page.server.ts"
    unit_page = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "[unitId]" / "+page.svelte"
    members_loader = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "members" / "+page.server.ts"
    )
    members_page = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "members" / "+page.svelte"
    )

    for path in (unit_loader, unit_page, members_loader, members_page):
        assert path.is_file(), f"Missing teacher detail page: {path}"

    unit_loader_source = unit_loader.read_text(encoding="utf-8")
    assert "/api/teaching/units/" in unit_loader_source
    assert "/sections" in unit_loader_source

    members_loader_source = members_loader.read_text(encoding="utf-8")
    assert "/api/teaching/views/courses/" in members_loader_source
    assert "/context" in members_loader_source
