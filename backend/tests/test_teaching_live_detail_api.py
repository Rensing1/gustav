"""
Teaching API — Latest submission detail (owner)

Contract-first tests for fetching the latest submission of a given student for
a task within a unit and course. Owner-only and privacy-preserving.
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
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402
from utils.db import require_db_or_skip as _require_db_or_skip  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


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
async def test_latest_detail_requires_owner_and_valid_ids():
    main.SESSION_STORE = SessionStore()
    async with (await _client()) as c:
        # unauthenticated
        r = await c.get(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/tasks/00000000-0000-0000-0000-000000000000/students/s/submissions/latest"
        )
        assert r.status_code == 401

    student = main.SESSION_STORE.create(sub="s-detail", name="Schüler", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/tasks/{uuid.uuid4()}/students/{student.sub}/submissions/latest"
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_latest_detail_happy_path_and_no_content_cases():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for detail tests")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-detail-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-detail-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Detail")
        unit = await _create_unit(c_owner, "Einheit Detail")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Initially: 204 No Content
        r_none = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
        )
        assert r_none.status_code in (204, 404)

        # Release & student submits a text
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Das ist eine Antwort."},
        )
        # Async submission acceptance
        assert r_sub.status_code in (200, 201, 202)

        r_detail = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
        )
        assert r_detail.status_code == 200
        body = r_detail.json()
        assert body["id"]
        assert body["task_id"] == task["id"]
        assert body["student_sub"] == learner.sub
        assert body["kind"] in ("text", "file", "image", "pdf")
        # For text submissions, expect a body
        if body["kind"] == "text":
            assert isinstance(body.get("text_body"), str) and len(body["text_body"]) > 0
