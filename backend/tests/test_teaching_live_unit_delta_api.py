"""
Teaching API — Live Unit Delta (Polling)

Contract-first tests for the polling-based delta endpoint that replaces the
earlier SSE stream. The endpoint returns only changed submission cells since
`updated_since`, enabling the UI to refresh efficiently.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import logging

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

from utils.db import require_db_or_skip as _require_db_or_skip


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
async def test_delta_requires_auth_and_owner():
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as c:
        # Unauthenticated
        r = await c.get(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/submissions/delta",
            params={"updated_since": datetime.now(timezone.utc).isoformat()},
        )
        assert r.status_code == 401

    student = main.SESSION_STORE.create(sub="s-delta", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/submissions/delta",
            params={"updated_since": datetime.now(timezone.utc).isoformat()},
        )
        assert r.status_code == 403

    _require_db_or_skip()
    logging.getLogger("gustav.web.teaching").setLevel(logging.DEBUG)
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for delta tests")

    owner = main.SESSION_STORE.create(sub="t-delta-owner", name="Owner", roles=["teacher"])  # type: ignore
    other = main.SESSION_STORE.create(sub="t-delta-other", name="Other", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        course_id = await _create_course(c, "Kurs Delta")
        unit = await _create_unit(c, "Einheit Delta")
        await _attach_unit(c, course_id, unit["id"])

        # Invalid timestamp
        bad = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/delta",
            params={"updated_since": "not-a-timestamp"},
        )
        assert bad.status_code == 400

        # Non-owner
        c.cookies.set(main.SESSION_COOKIE_NAME, other.session_id)
        r = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/delta",
            params={"updated_since": datetime.now(timezone.utc).isoformat()},
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_delta_returns_cells_after_submission():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for delta tests")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-delta-owner2", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-delta-learner", name="Student", roles=["student"])  # type: ignore

    async with (await _client()) as owner_client, (await _client()) as student_client:
        owner_client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        student_client.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        course_id = await _create_course(owner_client, "Delta Kurs")
        unit = await _create_unit(owner_client, "Delta Einheit")
        section = await _create_section(owner_client, unit["id"], "Abschnitt")
        task = await _create_task(owner_client, unit["id"], section["id"], "### Aufgabe")
        module = await _attach_unit(owner_client, course_id, unit["id"])
        await _add_member(owner_client, course_id, learner.sub)

        # Release section so submissions are possible
        r_vis = await owner_client.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        base_ts = datetime.now(timezone.utc).isoformat()

        # Initial delta should be empty (204)
        r_empty = await owner_client.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/delta",
            params={"updated_since": base_ts},
        )
        assert r_empty.status_code == 204

        # Student submits
        student_response = await student_client.post(
            f"/api/learning/courses/{course_id}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Meine Lösung"},
        )
        assert student_response.status_code in (200, 201, 202)

        # Owner fetches delta again
        r_delta = await owner_client.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 200
        body = r_delta.json()
        cells = body["cells"]
        assert cells, "expected at least one cell"
        cell = cells[0]
        assert cell["student_sub"] == learner.sub
        assert cell["task_id"] == task["id"]
        assert cell["has_submission"] is True
        assert cell["changed_at"]

        # Subsequent poll with newer timestamp should return 204
        next_ts = cell["changed_at"]
        r_again = await owner_client.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/delta",
            params={"updated_since": next_ts},
        )
        assert r_again.status_code == 204
