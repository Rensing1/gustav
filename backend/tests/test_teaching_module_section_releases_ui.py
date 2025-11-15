"""
Teaching UI — SSR toggles for section releases (HTMX flow)

Scenarios:
- Owner sees toggle page and can enable/disable a section; enabling shows a timestamp.
- Missing CSRF on toggle SSR route returns 403.
- Modules page contains a link to the toggle page.
"""
from __future__ import annotations

import re
import pytest
import httpx
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Unit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Abschnitt") -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


@pytest.mark.anyio
async def test_teacher_can_toggle_section_and_timestamp_is_shown():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-toggle", name="Lehrkraft", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Toggle Kurs")
        unit = await _create_unit(c, "Toggle Unit")
        s1 = await _create_section(c, unit["id"], "A1")
        await _create_section(c, unit["id"], "A2")
        module = await _attach_unit(c, course_id, unit["id"])

        # Teacher visits module sections page
        page = await c.get(f"/courses/{course_id}/modules/{module['id']}/sections")
        assert page.status_code == 200
        html = page.text
        # Extract CSRF token from the page
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert m, "csrf_token not found in page"
        csrf_token = m.group(1)
        # Initially, no timestamp is shown
        assert "Freigegeben am" not in html

        # Toggle section s1 to visible via SSR endpoint
        res = await c.post(
            f"/courses/{course_id}/modules/{module['id']}/sections/{s1['id']}/toggle",
            data={"csrf_token": csrf_token, "visible": "on"},
        )
        assert res.status_code == 200
        partial = res.text
        assert "id=\"module-sections\"" in partial
        # Timestamp should appear
        assert "Freigegeben am" in partial
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", partial)

        # Toggle off (no visible field)
        res2 = await c.post(
            f"/courses/{course_id}/modules/{module['id']}/sections/{s1['id']}/toggle",
            data={"csrf_token": csrf_token},
        )
        assert res2.status_code == 200
        partial2 = res2.text
        assert "Freigegeben am" not in partial2

        # Reload page should reflect latest persisted state (hidden)
        page2 = await c.get(f"/courses/{course_id}/modules/{module['id']}/sections")
        assert page2.status_code == 200
        assert "Freigegeben am" not in page2.text


@pytest.mark.anyio
async def test_toggle_without_csrf_is_forbidden():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-toggle-csrf", name="Lehrkraft", roles=["teacher"])
    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs")
        unit = await _create_unit(c, "Unit")
        sec = await _create_section(c, unit["id"], "A1")
        module = await _attach_unit(c, course_id, unit["id"])
        # Missing csrf_token
        r = await c.post(
            f"/courses/{course_id}/modules/{module['id']}/sections/{sec['id']}/toggle",
            data={"visible": "on"},
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_modules_page_contains_link_to_toggle_page():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-toggle-link", name="Lehrkraft", roles=["teacher"])
    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c)
        unit = await _create_unit(c)
        module = await _attach_unit(c, course_id, unit["id"])
        page = await c.get(f"/courses/{course_id}/modules")
        assert page.status_code == 200
        assert f"/courses/{course_id}/modules/{module['id']}/sections" in page.text


@pytest.mark.anyio
async def test_toggle_non_owner_returns_403():
    """Non-owner teacher submits SSR toggle → 403 is propagated from API."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-owner", name="Owner", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="t-other", name="Other", roles=["teacher"])

    async with (await _client()) as c:
        # Owner creates course/module/section
        c.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(c, "Kurs")
        unit = await _create_unit(c, "Unit")
        sec = await _create_section(c, unit["id"], "A1")
        module = await _attach_unit(c, course_id, unit["id"])

        # Other teacher visits the page to obtain CSRF (page may be mostly empty)
        c.cookies.set("gustav_session", other.session_id)
        page = await c.get(f"/courses/{course_id}/modules/{module['id']}/sections")
        assert page.status_code == 200
        m = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert m, "csrf_token not found"
        csrf_token = m.group(1)

        # Attempt toggle -> expect 403
        r = await c.post(
            f"/courses/{course_id}/modules/{module['id']}/sections/{sec['id']}/toggle",
            data={"csrf_token": csrf_token, "visible": "on"},
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_toggle_section_not_in_module_returns_404():
    """Owner toggles a section that does not belong to the module's unit → 404."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-owner-404", name="Owner", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(c, "Kurs")
        unit_a = await _create_unit(c, "UnitA")
        unit_b = await _create_unit(c, "UnitB")
        sec_a = await _create_section(c, unit_a["id"], "A1")  # noqa: F841
        sec_b = await _create_section(c, unit_b["id"], "B1")
        module = await _attach_unit(c, course_id, unit_a["id"])  # module references UnitA

        # Load toggle page to get CSRF
        page = await c.get(f"/courses/{course_id}/modules/{module['id']}/sections")
        m = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert m, "csrf_token not found"
        csrf_token = m.group(1)

        # Try toggling sec_b (from UnitB) in module of UnitA → 404
        r = await c.post(
            f"/courses/{course_id}/modules/{module['id']}/sections/{sec_b['id']}/toggle",
            data={"csrf_token": csrf_token, "visible": "on"},
        )
        assert r.status_code == 404
