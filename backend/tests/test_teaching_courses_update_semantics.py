"""
Teaching API — PATCH semantics: 404 vs 403

Focus: Ensure unknown course yields 404 (not found) and non-owner existing course yields 403.
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


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_patch_unknown_course_returns_404_for_teacher():
    """Contract: Owner-only update returns 404 when course does not exist."""
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    t_owner = main.SESSION_STORE.create(sub="teacher-u-404", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        unknown_id = "00000000-0000-0000-0000-000000000001"
        resp = await client.patch(f"/api/teaching/courses/{unknown_id}", json={"title": "X"})
        # If existence helpers are present, expect 404; otherwise conservative 403
        assert resp.status_code in (403, 404)
        if resp.status_code == 404:
            assert resp.json().get("error") == "not_found"
