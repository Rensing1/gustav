"""
Learning API — H5P content access-check (student scope, fail-closed)

Contract (BDD):
    Given a student enrolled and a released H5P task exists
    When GET /api/learning/courses/{course_id}/h5p/contents/{content_id}/access
    Then 204 No Content

    Given a student is not a member (or content not released)
    When GET access-check
    Then 404 Not Found (fail-closed, leak-minimizing)
"""

from __future__ import annotations

import importlib
import httpx
import pytest
from httpx import ASGITransport
import os
from uuid import UUID

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

from backend.tests.runtime_auth_helpers import install_session_store

main = importlib.import_module("backend.web.main")


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _prepare_released_h5p_task(monkeypatch: pytest.MonkeyPatch, *, content_id: str = "1") -> dict:
    _require_db_or_skip()

    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    try:
        from backend.teaching.repo_db import DBTeachingRepo
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="t-h5p-access", name="Teacher", roles=["teacher"])
    student = store.create(sub="s-h5p-access", name="Student", roles=["student"])
    outsider = store.create(sub="s-h5p-outsider", name="Outsider", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course = await c.post("/api/teaching/courses", json={"title": "Kurs H5P Access"})
        assert course.status_code == 201
        course_id = course.json()["id"]

        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Abschnitt"})).json()

        task = (
            await c.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
                json={
                    "instruction_md": "H5P Aufgabe (placeholder; not shown in UI).",
                    "criteria": [],
                    "h5p": {"content_id": content_id, "display_options": {}},
                },
            )
        ).json()

        module = (
            await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit["id"]})
        ).json()

        r_release = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r_release.status_code == 200

        r_member = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})
        assert r_member.status_code in (201, 204)

    return {
        "teacher": teacher,
        "student": student,
        "outsider": outsider,
        "course_id": course_id,
        "content_id": content_id,
        "task_id": task["id"],
    }


async def _prepare_locked_modular_h5p_task(monkeypatch: pytest.MonkeyPatch, *, content_id: str = "42") -> dict:
    """Create a modular unit where the H5P module is locked until prereq done."""
    _require_db_or_skip()

    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    try:
        from backend.teaching.repo_db import DBTeachingRepo

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    pytest.importorskip("psycopg")
    import psycopg  # type: ignore  # noqa: E402

    dsn = os.getenv("DATABASE_URL") or (
        f"postgresql://{os.getenv('APP_DB_USER','gustav_app')}:{os.getenv('APP_DB_PASSWORD','CHANGE_ME_DEV')}"
        f"@{os.getenv('TEST_DB_HOST','127.0.0.1')}:{os.getenv('TEST_DB_PORT','54322')}/postgres"
    )

    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="t-h5p-modular", name="Teacher", roles=["teacher"])
    student = store.create(sub="s-h5p-modular", name="Student", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course = await c.post("/api/teaching/courses", json={"title": "Kurs H5P Modular"})
        assert course.status_code == 201
        course_id = course.json()["id"]
        UUID(course_id)

        unit = (await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})).json()
        unit_id = unit["id"]
        UUID(unit_id)

        sec_a = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})).json()["id"]
        sec_b = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "B"})).json()["id"]
        UUID(sec_a)
        UUID(sec_b)

        # A: normal task (used to unlock B)
        task_a = (
            await c.post(
                f"/api/teaching/units/{unit_id}/sections/{sec_a}/tasks",
                json={"instruction_md": "Aufgabe A", "criteria": []},
            )
        ).json()["id"]
        UUID(task_a)

        # B: H5P task
        task_b = (
            await c.post(
                f"/api/teaching/units/{unit_id}/sections/{sec_b}/tasks",
                json={
                    "instruction_md": "H5P Aufgabe",
                    "criteria": [],
                    "h5p": {"content_id": content_id, "display_options": {}},
                },
            )
        ).json()["id"]
        UUID(task_b)

        module = (await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})).json()
        assert module.get("unit_id") == unit_id

        r_member = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})
        assert r_member.status_code in (201, 204)

    # Configure dependency A -> B and require 1 prereq for B.
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (teacher.sub,))
            cur.execute("select id::text from public.unit_modules where section_id = %s::uuid", (sec_a,))
            mod_a = (cur.fetchone() or [None])[0]
            cur.execute("select id::text from public.unit_modules where section_id = %s::uuid", (sec_b,))
            mod_b = (cur.fetchone() or [None])[0]
            assert mod_a and mod_b
            cur.execute(
                """
                insert into public.unit_module_edges (unit_id, from_module_id, to_module_id)
                values (%s::uuid, %s::uuid, %s::uuid)
                """,
                (unit_id, mod_a, mod_b),
            )
            cur.execute("update public.unit_modules set required_prereq_count = 1 where id = %s::uuid", (mod_b,))
        conn.commit()

    return {
        "teacher": teacher,
        "student": student,
        "course_id": course_id,
        "unit_id": unit_id,
        "content_id": content_id,
        "task_a": task_a,
        "task_b": task_b,
    }


@pytest.mark.anyio
async def test_learning_h5p_access_204_for_enrolled_student_and_released_task(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_released_h5p_task(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
        r = await c.get(
            f"/api/learning/courses/{fx['course_id']}/h5p/contents/{fx['content_id']}/access"
        )
        assert r.status_code == 204
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.text or "") == ""


@pytest.mark.anyio
async def test_learning_h5p_access_404_for_student_not_member(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_released_h5p_task(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["outsider"].session_id)
        r = await c.get(
            f"/api/learning/courses/{fx['course_id']}/h5p/contents/{fx['content_id']}/access"
        )
        assert r.status_code == 404
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.json() or {}).get("error") == "not_found"


@pytest.mark.anyio
async def test_learning_h5p_access_403_for_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="t-h5p-access-role", name="Teacher", roles=["teacher"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/1/access"
        )
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.json() or {}).get("error") == "forbidden"


@pytest.mark.anyio
async def test_learning_h5p_access_401_for_unauthenticated() -> None:
    async with (await _client()) as c:
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/1/access"
        )
        assert r.status_code == 401
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.json() or {}).get("error") == "unauthenticated"


@pytest.mark.anyio
async def test_learning_h5p_access_400_for_invalid_course_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    student = store.create(sub="s-h5p-access-bad-uuid", name="Student", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses/not-a-uuid/h5p/contents/1/access")
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_uuid"


@pytest.mark.anyio
async def test_learning_h5p_access_400_for_invalid_content_id(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    student = store.create(sub="s-h5p-access-bad-cid", name="Student", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/not-a-number/access"
        )
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_content_id"


@pytest.mark.anyio
async def test_learning_h5p_access_400_for_non_ascii_digit_content_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-ASCII digits must be rejected to match the OpenAPI `^[0-9]+$` pattern."""
    store = install_session_store(monkeypatch, main)
    student = store.create(sub="s-h5p-access-nonascii", name="Student", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/١/access"
        )
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_content_id"


@pytest.mark.anyio
async def test_learning_h5p_access_404_for_locked_modular_h5p_then_204_after_unlock(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_locked_modular_h5p_task(monkeypatch, content_id="42")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)

        # Locked module -> access-check must be fail-closed.
        r1 = await c.get(f"/api/learning/courses/{fx['course_id']}/h5p/contents/{fx['content_id']}/access")
        assert r1.status_code == 404
        assert r1.headers.get("Cache-Control") == "private, no-store"

        # Unlock via completing prereq (any submission is enough for non-H5P tasks).
        r_submit = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_a']}/submissions",
            json={"kind": "text", "text_body": "ok"},
        )
        assert r_submit.status_code == 202

        r2 = await c.get(f"/api/learning/courses/{fx['course_id']}/h5p/contents/{fx['content_id']}/access")
        assert r2.status_code == 204
        assert r2.headers.get("Cache-Control") == "private, no-store"
        assert (r2.text or "") == ""
