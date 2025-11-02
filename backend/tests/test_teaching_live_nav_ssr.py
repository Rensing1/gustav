"""
SSR Navigation — Ensure teachers can access the Live view via sidebar

We test two things:
1) The sidebar for a logged-in teacher contains a link to "/teaching/live".
2) The Live-Startseite "/teaching/live" is teacher-only and renders successfully.
"""
from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from pathlib import Path
import os

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
# Avoid requiring a working DB DSN for the Learning repo during import
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_sidebar_has_live_link_for_teacher():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-nav-live", name="Teacher", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/")
        assert r.status_code == 200
        html = r.text
        assert 'href="/teaching/live"' in html, "Sidebar should expose Live link for teachers"


@pytest.mark.anyio
async def test_teaching_live_route_teacher_only():
    main.SESSION_STORE = SessionStore()

    # Unauthenticated → redirect to login
    async with (await _client()) as c:
        r = await c.get("/teaching/live")
        assert r.status_code in (302, 303)  # redirect to /auth/login

    # Student → redirect to homepage
    student = main.SESSION_STORE.create(sub="s-nav-live", name="Student", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/teaching/live")
        assert r.status_code in (302, 303)

    # Teacher → 200 OK
    teacher = main.SESSION_STORE.create(sub="t-nav-live2", name="Teacher", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/teaching/live")
        assert r.status_code == 200
        assert "Unterricht" in r.text and "Live" in r.text


@pytest.mark.anyio
async def test_teaching_live_page_shows_course_and_unit_picker():
    # Requires DB-backed repos
    from utils.db import require_db_or_skip as _require_db_or_skip
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-nav-live3", name="Teacher", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Create course + unit + attach
        rc = await c.post("/api/teaching/courses", json={"title": "Kurs A"})
        assert rc.status_code == 201, rc.text
        course_id = rc.json()["id"]
        ru = await c.post("/api/teaching/units", json={"title": "Einheit A"})
        assert ru.status_code == 201, ru.text
        unit_id = ru.json()["id"]
        ra = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        assert ra.status_code == 201, ra.text

        # Live page should list the course in a picker
        page = await c.get("/teaching/live")
        assert page.status_code == 200
        html = page.text
        assert "Kurs A" in html

        # Units partial should list the attached unit
        units_partial = await c.get(f"/teaching/live/units", params={"course_id": course_id})
        assert units_partial.status_code == 200
        assert "Einheit A" in units_partial.text

        # Open button redirects to unit live page
        open_resp = await c.get(
            "/teaching/live/open", params={"course_id": course_id, "unit_id": unit_id}
        )
        assert open_resp.status_code in (302, 303)
        target = open_resp.headers.get("location", "")
        assert target.endswith(f"/teaching/courses/{course_id}/units/{unit_id}/live")

        # Follow the redirect
        follow = await c.get(target)
        assert follow.status_code == 200
        assert "Unterricht – Live" in follow.text or "Live-Ansicht" in follow.text
