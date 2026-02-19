"""
SSR UI — Scratch tasks are SB3 upload-only (MVP)

Intent:
    Ensure `Task.kind="scratch"` is rendered as an upload-only task in the
    student UI (no text mode, no textarea) and accepts `.sb3`.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import uuid

import pytest
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _prepare_scratch_fixture() -> tuple[str, str, str]:
    """Create a course/unit with one released scratch task and return (student_sid, course_id, unit_id)."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = (await c.post("/api/teaching/courses", json={"title": "Kurs"})).json()["id"]
        unit_id = (await c.post("/api/teaching/units", json={"title": "Einheit"})).json()["id"]
        section_id = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Abschnitt"})).json()[
            "id"
        ]
        _ = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "### Scratch Aufgabe", "criteria": ["K1"], "scratch": {}},
        )
        module = (await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})).json()
        r = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section_id}/visibility",
            json={"visible": True},
        )
        assert r.status_code == 200
        r = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})  # type: ignore[attr-defined]
        assert r.status_code in (201, 204)

    return student.session_id, course_id, unit_id


@pytest.mark.anyio
async def test_ui_renders_scratch_tasks_as_sb3_upload_only() -> None:
    sid, course_id, unit_id = await _prepare_scratch_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}")
    assert r.status_code == 200
    html = r.text

    # Scratch tasks: no mode switch + no textarea
    assert 'name="text_body"' not in html
    assert re.search(r'name=\"mode\"[^>]*value=\"text\"', html) is None

    # Must render upload input and preselect upload mode via hidden field
    assert re.search(r'name=\"upload_file\"', html), "upload input must be present"
    assert 'accept=".sb3,application/x.scratch.sb3"' in html
    assert re.search(r'type=\"hidden\"[^>]*name=\"mode\"[^>]*value=\"upload\"', html)

