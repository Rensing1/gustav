"""
SSR UI: /units (Lehrkräfte) – TDD: RED first

Ziel: Minimalen SSR‑Flow für Lerneinheitenliste und Anlegen via PRG validieren.
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

from identity_access.stores import SessionStore  # type: ignore
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


# Ensure tests use the in-memory session store – avoids DB dependency.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


async def _seed_unit(client: httpx.AsyncClient, *, title: str, teacher_session_cookie: str) -> None:
    client.cookies.set(main.SESSION_COOKIE_NAME, teacher_session_cookie)
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201, resp.text


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_units_page_requires_teacher_role():
    # Arrange: authenticated student session
    sess = main.SESSION_STORE.create(sub="s-301", name="Schülerin U", roles=["student"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/units", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers.get("location") == "/"


@pytest.mark.anyio
async def test_units_page_lists_units():
    # Arrange: authenticated teacher session and two units
    sess = main.SESSION_STORE.create(sub="t-302", name="Lehrer U1", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        await _seed_unit(c, title="Photosynthese", teacher_session_cookie=sess.session_id)
        await _seed_unit(c, title="  Zellatmung  ", teacher_session_cookie=sess.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/units")

    assert r.status_code == 200
    html = r.text
    assert "Photosynthese" in html
    assert "Zellatmung" in html
    cache = r.headers.get("Cache-Control", "")
    assert "private" in cache and "no-store" in cache


@pytest.mark.anyio
async def test_units_create_prg_success():
    sess = main.SESSION_STORE.create(sub="t-303", name="Lehrer U2", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        get_r = await c.get("/units")
        assert get_r.status_code == 200
        token = _extract_csrf_token(get_r.text)
        assert token, "csrf_token not found in form"

        post_r = await c.post(
            "/units",
            data={"title": "Genetik", "csrf_token": token},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert post_r.status_code in (302, 303)
        assert post_r.headers.get("location", "").startswith("/units")

        list_r = await c.get("/units")
        assert list_r.status_code == 200
        assert "Genetik" in list_r.text


@pytest.mark.anyio
async def test_units_create_validation_error():
    sess = main.SESSION_STORE.create(sub="t-304", name="Lehrer U3", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        get_r = await c.get("/units")
        token = _extract_csrf_token(get_r.text) or ""

        post_r = await c.post(
            "/units",
            data={"title": "", "csrf_token": token},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert post_r.status_code == 200
    assert "form-error" in post_r.text or "role=\"alert\"" in post_r.text


@pytest.mark.anyio
async def test_units_csrf_required_on_post():
    sess = main.SESSION_STORE.create(sub="t-305", name="Lehrer U4", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.post(
            "/units",
            data={"title": "Ökologie"},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert r.status_code == 403


@pytest.mark.anyio
async def test_units_list_escapes_title_xss():
    sess = main.SESSION_STORE.create(sub="t-306", name="Lehrer U5", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        await _seed_unit(c, title="<script>alert(1)</script>", teacher_session_cookie=sess.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/units")

    assert r.status_code == 200
    html = r.text
    assert "<script" not in html
    assert "&lt;script" in html


@pytest.mark.anyio
async def test_units_list_cache_headers_private_no_store():
    sess = main.SESSION_STORE.create(sub="t-307", name="Lehrer U6", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/units")

    assert r.status_code == 200
    cache = r.headers.get("Cache-Control", "")
    assert "private" in cache and "no-store" in cache


@pytest.mark.anyio
async def test_units_pagination_clamps_limit_offset_and_links_render():
    sess = main.SESSION_STORE.create(sub="t-308", name="Lehrer U7", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        for i in range(60):
            await _seed_unit(c, title=f"Unit {i+1}", teacher_session_cookie=sess.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)

        r = await c.get("/units?limit=999&offset=-1")

    assert r.status_code == 200
    html = r.text
    assert "href=\"/units?limit=50&offset=50\"" in html
    assert ("data-testid=\"pager-prev\"" not in html) or ("aria-disabled=\"true\"" in html)


@pytest.mark.anyio
async def test_units_create_form_includes_method_and_action_attributes():
    """The create-unit form must degrade gracefully without HTMX by using POST + action."""
    session = main.SESSION_STORE.create(sub="teacher-units-form", name="Teacher Units", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session.session_id)
        response = await client.get("/units")

    assert response.status_code == 200
    html = response.text
    assert 'method="post"' in html, "Create-unit form must declare method=post for non-HTMX submits"
    assert 'action="/units"' in html, "Create-unit form must declare action=/units for graceful fallback"


@pytest.mark.anyio
async def test_units_list_renders_target_wrapper_even_when_empty():
    """The HTMX target #unit-list-section must exist, even with zero units."""
    session = main.SESSION_STORE.create(sub="teacher-units-empty", name="Teacher Empty Units", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session.session_id)
        response = await client.get("/units")

    assert response.status_code == 200
    html = response.text
    assert 'id="unit-list-section"' in html, "Unit list wrapper is required for initial HTMX swaps"
    assert "Noch keine Lerneinheiten vorhanden." in html, "Empty state should be rendered for clarity"
