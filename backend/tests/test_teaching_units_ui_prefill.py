"""
SSR UI: Edit form for Lerneinheiten must prefill via GET /api/teaching/units/{id}

Scenario: When a teacher owns >50 units, the edit form must fetch the specific
unit by id (not rely on a first-page list) so the title is correctly prefilled.

Also validates that POST /units/{id}/edit requires CSRF.
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


def _extract_value(html: str, field: str) -> str | None:
    m = re.search(rf'id=\"{re.escape(field)}\"[^>]*value=\"([^\"]*)\"', html)
    return m.group(1) if m else None


def _extract_hidden_token(html: str, name: str) -> str | None:
    pattern = rf'name="{re.escape(name)}"\s+value="([^"]+)"'
    m = re.search(pattern, html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_unit_edit_prefill_uses_get_by_id_beyond_first_page():
    # Arrange: teacher with 55 units; target is #55 (outside first 50)
    sess = main.SESSION_STORE.create(sub="t-unit-prefill-1", name="Lehrer", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        created: list[tuple[str, str]] = []
        for i in range(55):
            title = f"Einheit {i+1}"
            r = await c.post("/api/teaching/units", json={"title": title})
            assert r.status_code == 201
            body = r.json()
            created.append((body["id"], title))
        uid, expected_title = created[50]

        # Act: open edit form and assert prefill equals the target unit
        r_form = await c.get(f"/units/{uid}/edit")
        assert r_form.status_code == 200
        title_value = _extract_value(r_form.text, "title")

    assert title_value == expected_title


@pytest.mark.anyio
async def test_unit_edit_invalid_payload_shows_error_message():
    sess = main.SESSION_STORE.create(sub="t-unit-edit-err-1", name="Teacher", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "Physik"})
        assert r_unit.status_code == 201
        uid = r_unit.json()["id"]

        edit_page = await c.get(f"/units/{uid}/edit")
        assert edit_page.status_code == 200
        token = _extract_hidden_token(edit_page.text, "csrf_token") or ""

        resp = await c.post(
            f"/units/{uid}/edit",
            data={"csrf_token": token, "title": "   ", "summary": ""},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert resp.status_code == 400
    assert "invalid_title" in resp.text
    assert "form-error" in resp.text


@pytest.mark.anyio
async def test_unit_edit_csrf_required_on_post():
    sess = main.SESSION_STORE.create(sub="t-unit-csrf-1", name="Teacher", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.post("/api/teaching/units", json={"title": "Photosynthese"})
        assert r.status_code == 201
        uid = r.json()["id"]

        # Missing csrf_token must be rejected
        r_post = await c.post(
            f"/units/{uid}/edit",
            data={"title": "Biologie"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert r_post.status_code == 403
