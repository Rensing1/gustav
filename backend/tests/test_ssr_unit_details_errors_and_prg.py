"""
SSR UI hardening: unit details error mapping and PRG 303 on create.

Scenarios (RED):
- Non-author teacher visits /units/{id} -> 403 (not 404)
- POST /units (valid CSRF) redirects with 303 (PRG)
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


async def _client() -> httpx.AsyncClient:
    # Provide Origin for strict CSRF on Teaching API writes during setup
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_unit_details_non_author_returns_403():
    # Use in-memory repo to avoid DB requirement
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-owner-403", name="Owner", roles=["teacher"])  # type: ignore
    other = main.SESSION_STORE.create(sub="t-other-403", name="Other", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        # Create a unit via API as the owner
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.post("/api/teaching/units", json={"title": "Nicht deine Einheit"})
        assert r.status_code == 201
        uid = r.json()["id"]

        # Visit as the non-author teacher
        c.cookies.set(main.SESSION_COOKIE_NAME, other.session_id)
        page = await c.get(f"/units/{uid}")

    assert page.status_code == 403


@pytest.mark.anyio
async def test_units_create_redirect_uses_303():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-units-303", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Load units page to obtain CSRF token
        page = await c.get("/units")
        assert page.status_code == 200
        token = _extract_csrf_token(page.text) or ""
        # Submit create form (non-HTMX)
        r = await c.post(
            "/units",
            data={"title": "Neue Einheit", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert r.status_code == 303
