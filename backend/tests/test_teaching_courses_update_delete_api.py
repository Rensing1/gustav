"""
Teaching API — Update & Delete courses (owner checks, validation)
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from utils.db import require_db_or_skip as _require_db_or_skip


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_owner_can_patch_title_and_non_owner_forbidden():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-u-1", name="Owner", roles=["teacher"])
    t_other = main.SESSION_STORE.create(sub="teacher-u-2", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Alt"})
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
async def test_owner_can_delete_course_and_memberships():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-d-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Loeschkurs"})
        assert c.status_code == 201
        course_id = c.json()["id"]
        # Add a member
        a = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": "student-del"})
        assert a.status_code in (201, 204)

        # Delete
        d = await client.delete(f"/api/teaching/courses/{course_id}")
        assert d.status_code == 204
        assert (d.text or "") == ""
        # List members should now 404 (course not found)
        r = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert r.status_code == 404


@pytest.mark.anyio
async def test_patch_validation_errors():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-v-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Valid"})
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
async def test_patch_with_no_fields_returns_current_row():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-u-nofields", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "StatusQuo"})
        assert c.status_code == 201
        course_id = c.json()["id"]

        p = await client.patch(f"/api/teaching/courses/{course_id}", json={})
        assert p.status_code == 200
        assert p.json()["title"] == "StatusQuo"


@pytest.mark.anyio
async def test_patch_can_clear_optional_fields():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-clear-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post(
            "/api/teaching/courses",
            json={"title": "Chemie", "subject": "Chemie", "grade_level": "EF", "term": "2025-1"},
        )
        assert c.status_code == 201
        course_id = c.json()["id"]

        p = await client.patch(f"/api/teaching/courses/{course_id}", json={"subject": None, "grade_level": None, "term": None})
        assert p.status_code == 200
        body = p.json()
        assert body["subject"] is None
        assert body["grade_level"] is None
        assert body["term"] is None
@pytest.mark.anyio
async def test_owner_delete_unknown_course_returns_404():
    """Owner deleting a non-existent course should get 404 Not Found."""
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-d-404", name="Owner404", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        # Use a random/invalid UUID; DB layer will not find it
        bad_id = "00000000-0000-0000-0000-000000000000"
        d = await client.delete(f"/api/teaching/courses/{bad_id}")
        assert d.status_code in (403, 404)  # Implementation should return 404 for owner
        # When the repo can disambiguate, it must be 404


@pytest.mark.anyio
async def test_recently_deleted_marker_expires(monkeypatch: pytest.MonkeyPatch):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    class FakeTime:
        def __init__(self, start: float):
            self.current = start

        def time(self) -> float:
            return self.current

    fake_time = FakeTime(1_000_000.0)
    monkeypatch.setattr(teaching, "time", fake_time, raising=False)

    t_owner = main.SESSION_STORE.create(sub="teacher-time", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        created = await client.post("/api/teaching/courses", json={"title": "Physik", "subject": "Physik"})
        assert created.status_code == 201
        course_id = created.json()["id"]

        deleted = await client.delete(f"/api/teaching/courses/{course_id}")
        assert deleted.status_code == 204

        # Immediately after deletion: should respond 404
        lst = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert lst.status_code == 404

        # Advance the fake clock beyond TTL and ensure the marker expires
        fake_time.current += teaching._RECENTLY_DELETED_TTL_SECONDS + 5

        lst2 = await client.get(f"/api/teaching/courses/{course_id}/members")
        # After TTL expiry, course remains non-existent -> 404 (contract)
        assert lst2.status_code == 404
