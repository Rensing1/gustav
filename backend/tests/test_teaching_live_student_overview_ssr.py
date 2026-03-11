"""
SSR UI — Student live overview page (teacher)
"""
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
from utils.db import require_db_or_skip as _require_db_or_skip  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Abschnitt") -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction, "criteria": ["Kriterium 1"], "max_attempts": 3},
    )
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_student_live_overview_page_renders_grouped_units_and_empty_filter_state() -> None:
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-student-live-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ssr-student-live", name="Anna", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs SSR Schueler")
        unit = await _create_unit(c, "Einheit SSR Schueler")
        sec = await _create_section(c, unit["id"], "S1")
        await _create_task(c, unit["id"], sec["id"], "### Aufgabe SSR")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, learner.sub)

        page = await c.get(f"/teaching/courses/{cid}/students/{learner.sub}/live")
        assert page.status_code == 200, page.text
        assert "Unterricht" in page.text
        assert "Einheit SSR Schueler" in page.text
        assert "Aufgabe SSR" in page.text
        assert f'name="unit_ids" value="{unit["id"]}"' in page.text

        empty = await c.get(
            f"/teaching/courses/{cid}/students/{learner.sub}/live",
            params=[("unit_ids", "")],
        )
        assert empty.status_code == 200, empty.text
        assert "Keine Lerneinheiten ausgewaehlt" in empty.text
