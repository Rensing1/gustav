"""
Teaching API — Headers for module section releases listing.

Validates that owner-scoped GET responses include Vary: Origin for cache safety.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    # Provide Origin to satisfy strict CSRF for setup writes.
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


def _releases_path(course_id: str, module_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases"


async def _create_course(client: httpx.AsyncClient, title: str = "Mathematik 10A") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Funktionen") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _attach_unit_to_course(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    resp = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_releases_list_headers_vary_origin_owner_and_errors():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub="teacher-releases-owner", name="Owner", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-releases-other", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)
        cid = await _create_course(client)
        unit = await _create_unit(client)
        module = await _attach_unit_to_course(client, cid, unit["id"])

        # 200 owner
        r200 = await client.get(_releases_path(cid, module["id"]))
        assert r200.status_code == 200
        assert r200.headers.get("Vary") == "Origin"

        # 400 invalid UUID
        r400 = await client.get(_releases_path(cid, "not-a-uuid"))
        assert r400.status_code == 400
        assert r400.headers.get("Vary") == "Origin"

        # 404 unknown module id
        r404 = await client.get(_releases_path(cid, "00000000-0000-0000-0000-000000000001"))
        assert r404.status_code == 404
        assert r404.headers.get("Vary") == "Origin"

        # 403 non-owner
        client.cookies.set("gustav_session", other.session_id)
        r403 = await client.get(_releases_path(cid, module["id"]))
        assert r403.status_code == 403
        assert r403.headers.get("Vary") == "Origin"
