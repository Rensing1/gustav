from __future__ import annotations

import os
import contextlib
import httpx
from httpx import ASGITransport

import pytest
from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.anyio("asyncio")


@contextlib.asynccontextmanager
async def _client(app):
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://internal") as c:
        yield c


def _set_session_cookie(client: httpx.AsyncClient, sid: str) -> None:
    client.cookies.set("gustav_session", sid)


async def _prepare_fixture():
    # Import app and helpers lazily to avoid circular imports
    import main  # type: ignore
    from identity_access.stores import SessionStore  # type: ignore

    # Fresh session store per test
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-1", name="Teacher", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-1", name="Student", roles=["student"])  # type: ignore

    async with _client(main.app) as client:
        # Create course and learning items
        _set_session_cookie(client, teacher.session_id)
        course = (await client.post("/api/teaching/courses", json={"title": "Kurs"})).json()
        unit = (await client.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await client.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "S"})).json()
        task = (
            await client.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
                json={"instruction_md": "do", "max_attempts": 2},
            )
        ).json()
        module = (await client.post(f"/api/teaching/courses/{course['id']}/modules", json={"unit_id": unit["id"]})).json()
        await client.post(
            f"/api/teaching/courses/{course['id']}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        await client.post(
            f"/api/teaching/courses/{course['id']}/members",
            json={"student_sub": student.sub, "name": "S"},
        )

    return course["id"], task["id"], student.session_id, main.app


@pytest.mark.anyio
async def test_csrf_origin_rejects_when_not_trusting_proxy_headers():
    _require_db_or_skip()
    course_id, task_id, sid, app = await _prepare_fixture()

    # Ensure proxy headers are not trusted by default
    os.environ["GUSTAV_TRUST_PROXY"] = "false"

    async with _client(app) as client:
        _set_session_cookie(client, sid)
        res = await client.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            headers={
                "Origin": "http://public.example",
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Host": "public.example",
            },
            json={"kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_csrf_origin_accepts_forwarded_headers_when_trust_proxy_true():
    _require_db_or_skip()
    course_id, task_id, sid, app = await _prepare_fixture()

    os.environ["GUSTAV_TRUST_PROXY"] = "true"

    async with _client(app) as client:
        _set_session_cookie(client, sid)
        res = await client.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            headers={
                "Origin": "http://public.example",
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Host": "public.example",
            },
            json={"kind": "text", "text_body": "ok"},
        )

    # With trusted proxy headers, CSRF check must not block the request.
    # Downstream may still respond differently (e.g., 404/not_found) depending on DB state,
    # but CSRF must not yield 403 csrf_violation.
    if res.status_code == 403:
        assert res.json().get("detail") != "csrf_violation", res.text
