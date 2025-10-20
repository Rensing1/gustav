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


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_owner_can_patch_title_and_non_owner_forbidden():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    teaching.REPO = teaching._Repo()

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
    teaching.REPO = teaching._Repo()

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
        # List members should now 404 (course not found)
        r = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert r.status_code == 404


@pytest.mark.anyio
async def test_patch_validation_errors():
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    teaching.REPO = teaching._Repo()

    t_owner = main.SESSION_STORE.create(sub="teacher-v-1", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t_owner.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Valid"})
        assert c.status_code == 201
        course_id = c.json()["id"]

        # Empty title
        p1 = await client.patch(f"/api/teaching/courses/{course_id}", json={"title": ""})
        assert p1.status_code == 400
        # Too long title
        p2 = await client.patch(f"/api/teaching/courses/{course_id}", json={"title": "x" * 201})
        assert p2.status_code == 400

