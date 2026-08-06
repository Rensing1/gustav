"""
Teaching API — Update & Delete courses (owner checks, validation)
"""
from __future__ import annotations

import importlib
import pytest
import httpx
from httpx import ASGITransport


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


main = importlib.import_module("backend.web.main")
from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip
from backend.teaching.repo_db import DBTeachingRepo
teaching = importlib.import_module("backend.web.routes.teaching")


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_owner_can_patch_title_and_non_owner_forbidden(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-u-1", name="Owner", roles=["teacher"])
    t_other = store.create(sub="teacher-u-2", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Alt", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
        assert c.status_code == 201
        course_id = c.json()["id"]

        # Owner can patch
        p = await client.patch(f"/api/teaching/courses/{course_id}", json={"title": "Neu"})
        assert p.status_code == 200
        assert p.json()["title"] == "Neu"

        # Non-owner receives 403
        client.cookies.set("gustav_session", t_other.session_id)
        p2 = await client.patch(f"/api/teaching/courses/{course_id}", json={"title": "Fremd"})
        assert p2.status_code == 403


@pytest.mark.anyio
async def test_direct_course_delete_is_disabled(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-d-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Löschkurs", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
        assert c.status_code == 201
        course_id = c.json()["id"]
        d = await client.delete(f"/api/teaching/courses/{course_id}")
        assert d.status_code == 405
        r = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert r.status_code == 200


@pytest.mark.anyio
async def test_patch_validation_errors(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-v-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Valid", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
        assert c.status_code == 201
        course_id = c.json()["id"]

        # Empty title
        p1 = await client.patch(f"/api/teaching/courses/{course_id}", json={"title": ""})
        assert p1.status_code == 400
        assert p1.json().get("detail") == "invalid_field"
        # Too long title
        p2 = await client.patch(f"/api/teaching/courses/{course_id}", json={"title": "x" * 201})
        assert p2.status_code == 400
        assert p2.json().get("detail") == "invalid_field"


@pytest.mark.anyio
async def test_patch_with_no_fields_returns_current_row(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-u-nofields", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "StatusQuo", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
        assert c.status_code == 201
        course_id = c.json()["id"]

        p = await client.patch(f"/api/teaching/courses/{course_id}", json={})
        assert p.status_code == 200
        assert p.json()["title"] == "StatusQuo"


@pytest.mark.anyio
async def test_patch_can_clear_optional_fields(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-clear-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post(
            "/api/teaching/courses",
            json={"title": "Chemie", "subject": "Chemie", "grade_level": "EF", "term": "2025-1", "school_year_start": 2025},
        )
        assert c.status_code == 201
        course_id = c.json()["id"]

        rejected = await client.patch(f"/api/teaching/courses/{course_id}", json={"subject": None, "grade_level": None})
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "course_metadata_incomplete"

        p = await client.patch(f"/api/teaching/courses/{course_id}", json={"term": None})
        assert p.status_code == 200
        body = p.json()
        assert body["subject"] == "Chemie"
        assert body["grade_level"] == "EF"
        assert body["term"] is None
@pytest.mark.anyio
async def test_direct_delete_unknown_course_is_also_disabled(monkeypatch: pytest.MonkeyPatch):
    """No course may bypass the confirmed asynchronous deletion path."""
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-d-404", name="Owner404", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        # Use a random/invalid UUID; DB layer will not find it
        bad_id = "00000000-0000-0000-0000-000000000000"
        d = await client.delete(f"/api/teaching/courses/{bad_id}")
        assert d.status_code == 405


@pytest.mark.anyio
async def test_disabled_direct_delete_does_not_hide_course(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    try:
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = store.create(sub="teacher-time", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        created = await client.post("/api/teaching/courses", json={"title": "Physik", "subject": "Physik", "grade_level": "10", "school_year_start": 2026})
        assert created.status_code == 201
        course_id = created.json()["id"]

        deleted = await client.delete(f"/api/teaching/courses/{course_id}")
        assert deleted.status_code == 405
        lst = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert lst.status_code == 200
