"""
Smoke test for sections endpoints using the in-memory Teaching repo.

Why:
    Ensure the fallback `_Repo` implements the sections API surface so tests and
    local dev without Postgres do not crash with 500s.
"""
from __future__ import annotations

from pathlib import Path
import os

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_sections_crud_smoke_with_memory_repo():
    main.SESSION_STORE = SessionStore()
    # Swap to in-memory repo explicitly
    mem = teaching._Repo()  # type: ignore[attr-defined]
    teaching.set_repo(mem)

    teacher = main.SESSION_STORE.create(sub="teacher-mem-sections", name="Mem", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)

        # Create a unit (author-owned)
        r_unit = await client.post("/api/teaching/units", json={"title": "MemUnit"})
        assert r_unit.status_code == 201
        unit = r_unit.json()

        # Create a section
        r_sec = await client.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "A"})
        assert r_sec.status_code == 201
        sec = r_sec.json()

        # List sections
        r_list = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        assert r_list.status_code == 200
        assert [s["id"] for s in r_list.json()] == [sec["id"]]

        # Update section title
        r_up = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{sec['id']}", json={"title": "B"}
        )
        assert r_up.status_code == 200
        assert r_up.json()["title"] == "B"

        # Reorder single item (idempotent)
        r_re = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder", json={"section_ids": [sec["id"]]}
        )
        assert r_re.status_code == 200
        assert [s["position"] for s in r_re.json()] == [1]

        # Delete section
        r_del = await client.delete(f"/api/teaching/units/{unit['id']}/sections/{sec['id']}")
        assert r_del.status_code == 204
