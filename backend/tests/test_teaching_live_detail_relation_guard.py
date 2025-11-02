"""
Teaching API — Latest submission detail: relation guard

Verifies that the endpoint returns 404 when the task does not belong to the
unit that is attached to the course (owner scope).
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import os

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402
from utils.db import require_db_or_skip as _require_db_or_skip  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction, "criteria": ["Kriterium 1"]},
    )
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


@pytest.mark.anyio
async def test_latest_detail_404_when_task_not_in_unit():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-relation-owner", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)

        course_id = await _create_course(c, "Kurs Guard")
        unit_a = await _create_unit(c, "Einheit A")
        unit_b = await _create_unit(c, "Einheit B")
        sec_b = await _create_section(c, unit_b["id"], "Abschnitt B")
        task_b = await _create_task(c, unit_b["id"], sec_b["id"], "### Aufgabe B")
        await _attach_unit(c, course_id, unit_a["id"])

        # Query with unit A (attached) but task from unit B → 404
        r = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit_a['id']}/tasks/{task_b['id']}/students/s-sub/submissions/latest"
        )
        assert r.status_code == 404

