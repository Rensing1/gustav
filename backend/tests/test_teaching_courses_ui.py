"""Legacy SSR teacher courses entry should no longer be the product landing page."""

from __future__ import annotations

from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_courses_legacy_entry_returns_gone_for_teacher() -> None:
    store = SessionStore()
    main.SESSION_STORE = store
    rec = store.create(sub="teacher-legacy-courses", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, rec.session_id)
        response = await client.get("/courses")

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route" in response.text.lower()
    assert "/courses" in response.text


@pytest.mark.anyio
async def test_courses_legacy_entry_keeps_student_redirect() -> None:
    store = SessionStore()
    main.SESSION_STORE = store
    rec = store.create(sub="student-legacy-courses", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, rec.session_id)
        response = await client.get("/courses", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/"
