"""Legacy SSR section release helpers are retired in favor of SvelteKit."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/teaching/courses/00000000-0000-0000-0000-000000000000/units/11111111-1111-1111-1111-111111111111/live/sections-panel"),
        ("POST", "/teaching/courses/00000000-0000-0000-0000-000000000000/modules/22222222-2222-2222-2222-222222222222/sections/33333333-3333-3333-3333-333333333333/visibility"),
    ],
)
async def test_live_section_release_helpers_are_retired(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="teacher-live-sections-retired", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
      client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
      response = await client.request(method, path, data={"visible": "true", "unit_id": "11111111-1111-1111-1111-111111111111"})

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"
