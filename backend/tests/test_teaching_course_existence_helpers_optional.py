"""
Optional tests that assert 404 vs 403 semantics when existence helpers are available.

Skips when database is unavailable or when helper functions are not present.
"""
from __future__ import annotations

import os
import uuid
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


def _probe_db_and_helpers() -> bool:
    # Try DATABASE_URL, then default limited DSN (127.0.0.1:54322)
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    candidates = [os.getenv("DATABASE_URL"), f"postgresql://{user}:{password}@{host}:{port}/postgres"]
    try:
        import psycopg  # type: ignore
        for dsn in candidates:
            if not dsn:
                continue
            try:
                with psycopg.connect(dsn, connect_timeout=1) as conn:
                    with conn.cursor() as cur:
                        cur.execute("select public.course_exists(%s)", (uuid.uuid4(),))
                        _ = cur.fetchone()
                        cur.execute("select public.course_exists_for_owner(%s, %s)", ("owner", uuid.uuid4()))
                        _ = cur.fetchone()
                return True
            except Exception:
                continue
        return False
    except Exception:
        return False


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_list_members_unknown_course_returns_404_when_helpers_present():
    if not _probe_db_and_helpers():
        pytest.skip("DB or helper functions not available")

    main.SESSION_STORE = SessionStore()
    t_owner = main.SESSION_STORE.create(sub="teacher-helpers", name="Owner", roles=["teacher"])

    bad_id = "00000000-0000-0000-0000-000000000000"
    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        r = await client.get(f"/api/teaching/courses/{bad_id}/members")
        assert r.status_code == 404


@pytest.mark.anyio
async def test_add_member_unknown_course_returns_404_when_helpers_present():
    if not _probe_db_and_helpers():
        pytest.skip("DB or helper functions not available")

    main.SESSION_STORE = SessionStore()
    t_owner = main.SESSION_STORE.create(sub="teacher-helpers2", name="Owner", roles=["teacher"])

    bad_id = "00000000-0000-0000-0000-000000000000"
    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        r = await client.post(f"/api/teaching/courses/{bad_id}/members", json={"student_sub": "s-x"})
        assert r.status_code == 404
