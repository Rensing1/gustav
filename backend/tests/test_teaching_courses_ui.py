"""
SSR UI: /courses (Lehrkräfte) – TDD: RED first

Ziel: Minimalen SSR‑Flow für Kursliste und Anlegen via PRG validieren.
Fokus: Rollen‑Gate, CSRF‑Pflicht, Cache‑Header, XSS‑Escaping, Pagination‑Clamp.

Hinweis: Tests seeden Daten über die interne Teaching‑API, um das in‑process
Repo zu verwenden, ohne externe Abhängigkeiten einzuführen.
"""

from __future__ import annotations

import re
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
from routes import teaching as teaching_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


# Ensure tests use the in-memory session store – avoids DB dependency.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


async def _seed_course(client: httpx.AsyncClient, *, title: str, teacher_session_cookie: str) -> None:
    # API uses authenticated teacher identity from middleware; provide cookie.
    client.cookies.set(main.SESSION_COOKIE_NAME, teacher_session_cookie)
    resp = await client.post("/api/teaching/courses", json={"title": title}, headers={"Origin": "http://test"})
    assert resp.status_code == 201, resp.text


async def _list_courses(client: httpx.AsyncClient, *, teacher_session_cookie: str) -> list[dict]:
    client.cookies.set(main.SESSION_COOKIE_NAME, teacher_session_cookie)
    r = await client.get("/api/teaching/courses")
    assert r.status_code == 200
    return r.json()


def _extract_csrf_token(html: str) -> str | None:
    # Hidden input, name=csrf_token
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_courses_page_requires_teacher_role():
    # Arrange: authenticated student session
    sess = main.SESSION_STORE.create(sub="s-101", name="Schülerin A", roles=["student"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/courses", follow_redirects=False)

    # Non‑teacher must be redirected away from teacher view
    assert r.status_code == 303
    assert r.headers.get("location") == "/"


@pytest.mark.anyio
async def test_courses_page_lists_courses():
    # Arrange: authenticated teacher session and two courses
    sess = main.SESSION_STORE.create(sub="t-201", name="Lehrer B", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        await _seed_course(c, title="Biologie 7", teacher_session_cookie=sess.session_id)
        await _seed_course(c, title="  Chemie 8  ", teacher_session_cookie=sess.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/courses")

    assert r.status_code == 200
    html = r.text
    # Titles must appear (trimmed, escaped by components)
    assert "Biologie 7" in html
    assert "Chemie 8" in html
    # SSR pages must be non‑cacheable (privacy)
    cache = r.headers.get("Cache-Control", "")
    assert "private" in cache and "no-store" in cache


@pytest.mark.anyio
async def test_courses_create_prg_success():
    # Arrange: teacher session
    sess = main.SESSION_STORE.create(sub="t-202", name="Lehrer C", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        get_r = await c.get("/courses")
        assert get_r.status_code == 200
        token = _extract_csrf_token(get_r.text)
        # Expect synchronizer token in form (Iteration 1A requirement)
        assert token, "csrf_token not found in form"

        # Act: POST form (PRG)
        post_r = await c.post(
            "/courses",
            data={"title": "Informatik 10", "csrf_token": token},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Assert: PRG redirect back to listing
        assert post_r.status_code in (302, 303)
        assert post_r.headers.get("location", "").startswith("/courses")

        # Follow redirect and see new course
        list_r = await c.get("/courses")
        assert list_r.status_code == 200
        assert "Informatik 10" in list_r.text


@pytest.mark.anyio
async def test_courses_create_validation_error():
    # Arrange: teacher session and csrf token
    sess = main.SESSION_STORE.create(sub="t-203", name="Lehrer D", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        get_r = await c.get("/courses")
        token = _extract_csrf_token(get_r.text) or ""

        # Act: missing title triggers validation error, no redirect
        post_r = await c.post(
            "/courses",
            data={"title": "", "csrf_token": token},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert post_r.status_code == 200
    # Expect inline error marker (class/role) and preserved form
    assert "form-error" in post_r.text or "role=\"alert\"" in post_r.text


@pytest.mark.anyio
async def test_courses_csrf_required_on_post():
    # Arrange: teacher session
    sess = main.SESSION_STORE.create(sub="t-204", name="Lehrer E", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Act: POST without csrf token
        r = await c.post(
            "/courses",
            data={"title": "Physik 9"},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    # Assert: forbidden due to missing/invalid CSRF
    assert r.status_code == 403


@pytest.mark.anyio
async def test_courses_list_escapes_title_xss():
    # Arrange: seed course with XSS payload
    sess = main.SESSION_STORE.create(sub="t-205", name="Lehrer F", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        await _seed_course(c, title="<script>alert(1)</script>", teacher_session_cookie=sess.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/courses")

    assert r.status_code == 200
    html = r.text
    assert "<script" not in html
    assert "&lt;script" in html


@pytest.mark.anyio
async def test_courses_list_cache_headers_private_no_store():
    sess = main.SESSION_STORE.create(sub="t-206", name="Lehrer G", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/courses")

    assert r.status_code == 200
    cache = r.headers.get("Cache-Control", "")
    assert "private" in cache and "no-store" in cache


@pytest.mark.anyio
async def test_courses_pagination_clamps_limit_offset_and_links_render():
    # Arrange: seed > 50 courses
    sess = main.SESSION_STORE.create(sub="t-207", name="Lehrer H", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        for i in range(60):
            await _seed_course(c, title=f"Kurs {i+1}", teacher_session_cookie=sess.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)

        # Manipulated URL params – must be clamped to limit=50, offset=0
        r = await c.get("/courses?limit=999&offset=-1")

    assert r.status_code == 200
    html = r.text
    # Expect a "Weiter" link to offset=50 with clamped limit
    assert "href=\"/courses?limit=50&offset=50\"" in html
    # And either a disabled "Zurück" or no prev link when offset=0
    assert ("data-testid=\"pager-prev\"" not in html) or ("aria-disabled=\"true\"" in html)


@pytest.mark.anyio
async def test_courses_create_htmx_from_empty_list_updates_list_section():
    # Arrange: teacher session with initially no courses
    sess = main.SESSION_STORE.create(sub="t-208", name="Lehrer I", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)

        # Initial GET renders the page; ensure wrapper for list exists even if empty
        r_get = await c.get("/courses")
        assert r_get.status_code == 200
        html = r_get.text
        assert 'id="course-list-section"' in html, "List wrapper must always be present"
        token = _extract_csrf_token(html) or ""

        # Act: HTMX POST to create the first course
        r_post = await c.post(
            "/courses",
            data={"title": "Informatik 11", "csrf_token": token},
            headers={
                "HX-Request": "true",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            follow_redirects=False,
        )
        # Assert: returns partial HTML containing the updated list wrapper and new title
        assert r_post.status_code == 200
        body = r_post.text
        assert 'id="course-list-section"' in body
        assert "Informatik 11" in body


@pytest.mark.anyio
async def test_courses_delete_htmx_updates_list_via_api_not_dummy():
    # Arrange: teacher with two real DB courses
    sess = main.SESSION_STORE.create(sub="t-209", name="Lehrer J", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        await _seed_course(c, title="Geschichte 7", teacher_session_cookie=sess.session_id)
        await _seed_course(c, title="Biologie 8", teacher_session_cookie=sess.session_id)
        courses = await _list_courses(c, teacher_session_cookie=sess.session_id)
        assert len(courses) >= 2
        # Pick one to delete
        to_delete = courses[0]["id"]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Fetch page for CSRF
        page = await c.get("/courses")
        token = _extract_csrf_token(page.text) or ""
        # Act: HTMX delete
        r = await c.post(
            f"/courses/{to_delete}/delete",
            data={"csrf_token": token},
            headers={"HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert r.status_code == 200
        body = r.text
        # Assert: updated list wrapper present and deleted title not present anymore
        assert 'id="course-list-section"' in body
        # Re-fetch from API to confirm deletion persisted
        courses_after = await _list_courses(c, teacher_session_cookie=sess.session_id)
        ids_after = {c["id"] for c in courses_after}
    assert to_delete not in ids_after


@pytest.mark.anyio
async def test_courses_edit_page_allows_patch_and_redirects():
    # Arrange: teacher + seed one course
    sess = main.SESSION_STORE.create(sub="t-210", name="Lehrer K", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        await _seed_course(c, title="Deutsch 6", teacher_session_cookie=sess.session_id)
        courses = await _list_courses(c, teacher_session_cookie=sess.session_id)
        cid = courses[0]["id"]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # GET edit form
        r_form = await c.get(f"/courses/{cid}/edit")
        assert r_form.status_code == 200
        token = _extract_csrf_token(r_form.text) or ""
        # Submit patch
        r_post = await c.post(
            f"/courses/{cid}/edit",
            data={"csrf_token": token, "title": "Deutsch 6a"},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r_post.status_code in (302, 303)
        assert r_post.headers.get("location", "").startswith("/courses")
        # Verify list reflects new title
        r_list = await c.get("/courses")
        assert r_list.status_code == 200
        assert "Deutsch 6a" in r_list.text
