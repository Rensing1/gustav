"""Legacy SSR learning entry should no longer act as the product landing page."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_learning_legacy_entry_returns_gone_for_student(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="student-legacy-learning", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, rec.session_id)
        response = await client.get("/learning")

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route" in response.text.lower()


@pytest.mark.anyio
async def test_learning_legacy_entry_keeps_teacher_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="teacher-legacy-learning", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, rec.session_id)
        response = await client.get("/learning", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/"
