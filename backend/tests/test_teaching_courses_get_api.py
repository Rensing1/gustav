"""
Teaching API: GET /api/teaching/courses/{id}

Given
- A teacher owns a course

When
- The owner fetches the course by id

Then
- The API returns 200 with the Course payload

And When
- A different teacher fetches the same id

Then
- The API returns 403 (forbidden)

And When
- The owner requests an unknown id

Then
- The API returns 404 (not found)
"""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from identity_access.stores import SessionStore
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


# Ensure tests use the in-memory session store – avoids DB dependency.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


async def _create_course(client: httpx.AsyncClient, *, title: str, teacher_cookie: str) -> str:
    client.cookies.set(main.SESSION_COOKIE_NAME, teacher_cookie)
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


@pytest.mark.anyio
async def test_get_course_by_id_owner_returns_200():
    owner = main.SESSION_STORE.create(sub="t-owner-1", name="Owner", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        cid = await _create_course(c, title="Physik 10", teacher_cookie=owner.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(f"/api/teaching/courses/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body.get("id") == cid
    assert body.get("title") == "Physik 10"


@pytest.mark.anyio
async def test_get_course_by_id_non_owner_returns_403():
    owner = main.SESSION_STORE.create(sub="t-owner-2", name="Owner", roles=["teacher"])
    intruder = main.SESSION_STORE.create(sub="t-other-2", name="Other", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        cid = await _create_course(c, title="Chemie 9", teacher_cookie=owner.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, intruder.session_id)
        r = await c.get(f"/api/teaching/courses/{cid}")
    assert r.status_code == 403


@pytest.mark.anyio
async def test_get_course_by_id_unknown_returns_404():
    owner = main.SESSION_STORE.create(sub="t-owner-3", name="Owner", roles=["teacher"])
    unknown = str(_uuid.uuid4())
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(f"/api/teaching/courses/{unknown}")
    assert r.status_code == 404
