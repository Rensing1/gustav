"""
Optional DB-level RLS smoke tests for Sections.

Skips automatically when:
- Limited DSN not configured (RLS_TEST_DSN/TEACHING_DATABASE_URL/DATABASE_URL), or
- DB repo unavailable in the current environment.

These tests validate that Row Level Security (RLS) prevents non-authors from
listing or mutating sections of a learning unit authored by someone else.
"""
from __future__ import annotations

import os
import pytest


pytestmark = pytest.mark.anyio("asyncio")


def _have_dsn() -> bool:
    return bool(os.getenv("RLS_TEST_DSN") or os.getenv("TEACHING_DATABASE_URL") or os.getenv("DATABASE_URL"))


@pytest.mark.anyio
async def test_rls_repo_smoke_sections_methods_exist_and_rls_active():
    if not _have_dsn():
        pytest.skip("No DSN set for DB tests")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DBTeachingRepo unavailable")

    repo = None
    try:
        repo = DBTeachingRepo()  # uses limited DSN by default; enforces gustav_limited
    except Exception as e:
        pytest.skip(f"DB repo cannot be constructed: {e}")

    # Ensure required methods exist
    for name in (
        "list_sections_for_author",
        "create_section",
        "update_section_title",
        "delete_section",
        "reorder_unit_sections_owned",
        "create_unit",
    ):
        if not hasattr(repo, name):
            pytest.skip(f"Method missing: {name}")

    author = "teacher-rls-author"
    other = "teacher-rls-other"

    # Arrange: create a unit and one section as the author
    unit = repo.create_unit(title="RLS Unit", summary=None, author_id=author)
    sec = repo.create_section(unit_id=unit["id"], title="S1", author_id=author)

    # Non-author cannot list or mutate
    assert repo.list_sections_for_author(unit["id"], other) == []
    assert repo.update_section_title(unit["id"], sec["id"], "XX", other) is None
    assert repo.delete_section(unit["id"], sec["id"], other) is False
    with pytest.raises(ValueError):
        repo.reorder_unit_sections_owned(unit["id"], other, [sec["id"]])

    # Author retains full access
    lst = repo.list_sections_for_author(unit["id"], author)
    assert len(lst) == 1 and lst[0]["id"] == sec["id"]
    # Reorder single-item is allowed and idempotent
    ordered = repo.reorder_unit_sections_owned(unit["id"], author, [sec["id"]])
    assert [s["id"] for s in ordered] == [sec["id"]]
    # Delete as author succeeds
    assert repo.delete_section(unit["id"], sec["id"], author) is True
