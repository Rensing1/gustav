"""
SSR UI: /courses/{course_id}/modules – Lerneinheiten zuordnen und sortieren

Ziele (TDD/RED):
- Seite rendert mit sortierbarer Modulliste und CSRF-Token
- Reorder per UI-Forwarder funktioniert (id=module_<uuid>)
- UI-POSTs (create/delete/reorder) erfordern CSRF
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


async def _create_course_via_api(client: httpx.AsyncClient, *, title: str) -> str:
    r = await client.post("/api/teaching/courses", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


async def _create_unit_via_api(client: httpx.AsyncClient, *, title: str) -> str:
    r = await client.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


@pytest.mark.anyio
async def test_course_modules_page_renders_and_reorder_changes_order():
    # Arrange: Lehrer-Session und Kurs mit 2 Modulen
    sess = main.SESSION_STORE.create(sub="t-ui-mod-1", name="Lehrer MOD1", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        course_id = await _create_course_via_api(c, title="UI-Kurs Modules")
        u1 = await _create_unit_via_api(c, title="Erste Einheit")
        u2 = await _create_unit_via_api(c, title="Zweite Einheit")
        m1 = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u1}, headers={"Origin": "http://test"})
        assert m1.status_code == 201
        m2 = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u2}, headers={"Origin": "http://test"})
        assert m2.status_code == 201

        page = await c.get(f"/courses/{course_id}/modules")
        assert page.status_code == 200
        assert page.headers.get("Cache-Control") == "private, no-store"
        body = page.text
        # Stable wrapper and sortable enabled
        assert 'id="module-list-section"' in body
        assert 'hx-ext="sortable"' in body
        token = _extract_csrf_token(body) or ""
        assert token

        # Load module ids via API (avoid brittle HTML parsing)
        lst = await c.get(f"/api/teaching/courses/{course_id}/modules")
        assert lst.status_code == 200
        mods = lst.json()
        # map unit_id -> module_id
        id_map = {m.get("unit_id"): m.get("id") for m in mods}
        m1_id = id_map.get(u1) or ""
        m2_id = id_map.get(u2) or ""
        assert m1_id and m2_id and m1_id != m2_id

        # Reorder: put m2 before m1
        form_body = f"id=module_{m2_id}&id=module_{m1_id}"
        rr = await c.post(
            f"/courses/{course_id}/modules/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
                "HX-Request": "true",
            },
        )
        assert rr.status_code in (200, 204)

        # Assert: Zweite Einheit erscheint vor Erste Einheit
        page2 = await c.get(f"/courses/{course_id}/modules")
        assert page2.status_code == 200
    body2 = page2.text
    assert body2.find("Zweite Einheit") < body2.find("Erste Einheit")


@pytest.mark.anyio
async def test_module_titles_link_to_unit_pages():
    sess = main.SESSION_STORE.create(sub="t-ui-mod-5", name="Lehrer MOD5", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        course_id = await _create_course_via_api(c, title="UI-Kurs Modules Links")
        u1 = await _create_unit_via_api(c, title="Verlinkte Einheit")
        r = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u1})
        assert r.status_code == 201

        page = await c.get(f"/courses/{course_id}/modules")
        assert page.status_code == 200
        html = page.text
        # Expect an anchor to the unit detail/sections management page
        assert f'href="/units/{u1}"' in html


@pytest.mark.anyio
async def test_modules_ui_posts_require_csrf():
    sess = main.SESSION_STORE.create(sub="t-ui-mod-2", name="Lehrer MOD2", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        course_id = await _create_course_via_api(c, title="UI-Kurs Modules CSRF")
        u = await _create_unit_via_api(c, title="Einheit CSRF")
        # Missing CSRF on create
        r1 = await c.post(
            f"/courses/{course_id}/modules/create",
            data={"unit_id": u},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        # Missing CSRF on delete
        mod = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u})
        assert mod.status_code == 201
        mid = mod.json().get("id")
        r2 = await c.post(
            f"/courses/{course_id}/modules/{mid}/delete",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        # Missing CSRF on reorder
        r3 = await c.post(
            f"/courses/{course_id}/modules/reorder",
            content="id=module_foo",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert r1.status_code == 403
    assert r2.status_code == 403
    assert r3.status_code == 403


@pytest.mark.anyio
async def test_delete_updates_available_units_oob():
    sess = main.SESSION_STORE.create(sub="t-ui-mod-3", name="Lehrer MOD3", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        course_id = await _create_course_via_api(c, title="UI-Kurs Modules OOB")
        u1 = await _create_unit_via_api(c, title="Einheit 1")
        u2 = await _create_unit_via_api(c, title="Einheit 2")
        # Attach u1 only
        mod = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u1})
        assert mod.status_code == 201

        page = await c.get(f"/courses/{course_id}/modules")
        token = _extract_csrf_token(page.text) or ""
        assert token
        # Find module id for u1 via API
        lst = await c.get(f"/api/teaching/courses/{course_id}/modules")
        m = next((it for it in lst.json() if it.get("unit_id") == u1), None)
        assert m and m.get("id")
        mid = m.get("id")

        # Delete via UI and expect OOB section includes Einheit 1 as available
        r = await c.post(
            f"/courses/{course_id}/modules/{mid}/delete",
            data={"csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded", "HX-Request": "true"},
        )
        assert r.status_code == 200
        body = r.text
        assert 'id="available-units-section"' in body and 'hx-swap-oob="true"' in body
        assert "Einheit 1" in body


@pytest.mark.anyio
async def test_create_updates_available_units_oob():
    sess = main.SESSION_STORE.create(sub="t-ui-mod-4", name="Lehrer MOD4", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        course_id = await _create_course_via_api(c, title="UI-Kurs Modules OOB2")
        u1 = await _create_unit_via_api(c, title="Einheit X")
        # Load page to get token
        page = await c.get(f"/courses/{course_id}/modules")
        token = _extract_csrf_token(page.text) or ""
        assert token

        # Create via UI
        r = await c.post(
            f"/courses/{course_id}/modules/create",
            data={"csrf_token": token, "unit_id": u1},
            headers={"Content-Type": "application/x-www-form-urlencoded", "HX-Request": "true"},
        )
        assert r.status_code == 200
        body = r.text
        # Available units OOB section should exclude Einheit X now
        assert 'id="available-units-section"' in body and 'hx-swap-oob="true"' in body
        # Not a strict parser: ensure Einheit X does not appear inside available-units-section snippet
        # by checking that the body contains the title only once (in module card) or not inside the OOB
        # For simplicity, assert not present at all in OOB when freshly attached
        oob_match = re.search(r'<section id=\"available-units-section\"[\s\S]*?</section>', body)
        assert oob_match is not None
        assert "Einheit X" not in oob_match.group(0)
