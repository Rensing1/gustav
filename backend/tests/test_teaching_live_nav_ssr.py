"""
SSR Navigation — legacy sidebar should not advertise old Live product paths.

The old FastAPI live picker is now retired. The new top-level entry lives in
SvelteKit under `/live`, while the remaining deep live detail flows still stay
temporarily in the backend adapter.
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
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_sidebar_hides_live_link_for_teacher():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-nav-live", name="Teacher", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/")
        assert r.status_code == 200
        html = r.text
        assert 'href="/teaching/live"' not in html, "Legacy sidebar should not expose Live link anymore"


@pytest.mark.anyio
async def test_teaching_live_legacy_entry_returns_gone_for_teacher() -> None:
    main.SESSION_STORE = SessionStore()

    teacher = main.SESSION_STORE.create(sub="t-nav-live2", name="Teacher", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/teaching/live")

    assert r.status_code == 410
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route" in r.text.lower()


@pytest.mark.anyio
async def test_teaching_live_legacy_helpers_are_retired_for_teacher() -> None:
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-nav-live3", name="Teacher", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        units_partial = await c.get("/teaching/live/units", params={"course_id": "course-1"})
        open_page = await c.get("/teaching/live/open", params={"course_id": "course-1", "unit_id": "unit-1"})

    assert units_partial.status_code == 410
    assert units_partial.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route" in units_partial.text.lower()
    assert open_page.status_code == 410
    assert open_page.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_teaching_live_legacy_entry_keeps_student_redirect() -> None:
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-nav-live", name="Student", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/teaching/live", follow_redirects=False)

    assert r.status_code in (302, 303)
