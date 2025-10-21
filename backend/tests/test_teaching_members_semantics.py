"""
Teaching API — Members semantics after delete: 404 vs 403

Focus: After an owner deletes a course, roster operations (add/remove/list) must
return 404 (Not Found), not 403 (Forbidden). This aligns clients and the
OpenAPI contract.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys
import os


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


def _require_db_or_skip():
    dsn = os.getenv("DATABASE_URL") or ""
    try:
        import psycopg  # type: ignore
        with psycopg.connect(dsn, connect_timeout=1):
            return
    except Exception:
        pytest.skip("Database not reachable; ensure migrations applied and DATABASE_URL set")


def _helpers_available_or_skip():
    """Skip when existence helpers are unavailable (can't disambiguate 404 vs 403 safely)."""
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = DBTeachingRepo()
        # Unknown ID should deterministically return False when helper is present; None means unavailable
        ok = repo.course_exists("00000000-0000-0000-0000-000000000001")
        if ok is None:
            pytest.skip("DB helpers unavailable; cannot assert precise 404 vs 403 semantics")
    except Exception:
        pytest.skip("DB repo unavailable")


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient) -> str:
    resp = await client.post("/api/teaching/courses", json={"title": "Physics", "subject": "phy"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _delete_course(client: httpx.AsyncClient, cid: str) -> None:
    resp = await client.delete(f"/api/teaching/courses/{cid}")
    assert resp.status_code == 204


@pytest.mark.anyio
async def test_add_member_after_delete_returns_404_for_owner():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()
    _helpers_available_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-u-add-404", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        cid = await _create_course(client)
        await _delete_course(client, cid)
        resp = await client.post(f"/api/teaching/courses/{cid}/members", json={"student_sub": "student-x"})
        assert resp.status_code == 404
        assert resp.json().get("error") == "not_found"


@pytest.mark.anyio
async def test_remove_member_after_delete_returns_404_for_owner():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()
    _helpers_available_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-u-rem-404", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        cid = await _create_course(client)
        await _delete_course(client, cid)
        resp = await client.delete(f"/api/teaching/courses/{cid}/members/student-x")
        assert resp.status_code == 404
        assert resp.json().get("error") == "not_found"


@pytest.mark.anyio
async def test_list_members_after_delete_returns_404_for_owner():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-u-list-404", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        cid = await _create_course(client)
        await _delete_course(client, cid)
        resp = await client.get(f"/api/teaching/courses/{cid}/members")
        assert resp.status_code == 404
        assert resp.json().get("error") == "not_found"

