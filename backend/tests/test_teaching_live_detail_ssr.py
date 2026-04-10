"""Legacy SSR live detail routes are retired in favor of SvelteKit."""

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
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_live_detail_fragment_is_retired_for_teachers() -> None:
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="teacher-live-detail-retired", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as client:
      client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
      response = await client.get(
          "/teaching/courses/00000000-0000-0000-0000-000000000000/units/11111111-1111-1111-1111-111111111111/live/detail",
          params={"student_sub": "student-1", "task_id": "task-1"},
      )

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route retired" in response.text.lower()
