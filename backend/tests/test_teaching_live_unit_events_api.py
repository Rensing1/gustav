"""
Teaching API — Live Unit Events (RED)

Server-Sent Events endpoint contract checks: authorization and basic stream
contract. Detailed event forwarding from DB triggers can be covered after the
minimal route exists.
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import os

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_events_requires_auth_and_owner():
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as c:
        r = await c.get(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/submissions/events"
        )
        assert r.status_code == 401

    student = main.SESSION_STORE.create(sub="s-live-events", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/submissions/events"
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_events_owner_can_connect_and_receives_sse_headers():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for SSE test")

    # Seed owner + course + unit and attach
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-live-sse", name="Owner", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs SSE"}, timeout=5)
        assert r_course.status_code == 201
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit SSE"}, timeout=5)
        assert r_unit.status_code == 201
        unit_id = r_unit.json()["id"]
        r_attach = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, timeout=5)
        assert r_attach.status_code == 201

        # Connect to SSE using streaming client; do not consume body
        async with c.stream(
            "GET",
            f"/api/teaching/courses/{course_id}/units/{unit_id}/submissions/events",
            headers={"Accept": "text/event-stream"},
            timeout=5,
        ) as r:
            assert r.status_code == 200
            assert r.headers.get("content-type", "").startswith("text/event-stream")
            # Security headers present
            assert r.headers.get("Cache-Control") == "private, no-store"
            assert r.headers.get("Vary") == "Origin"
