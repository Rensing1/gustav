"""
Teaching API — Live Unit Summary (RED)

Contract-first tests for the new live unit summary endpoint that powers the
teacher's classroom view. These tests intentionally fail until the endpoint
is implemented according to the OpenAPI contract and Clean Architecture.

Covers:
- AuthZ: 401 unauthenticated; 403 wrong role or non-owner; 404 unit not in course
- Happy path: minimal status matrix (has_submission true/false)
- Headers: private, no-store + Vary: Origin on 200
"""
from __future__ import annotations

import os
import uuid
import pytest
import psycopg
from psycopg import errors as psy_errors
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
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
async def test_summary_requires_auth_and_owner_role():
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as c:
        # Unauthenticated → 401
        r_unauth = await c.get(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/submissions/summary"
        )
        assert r_unauth.status_code == 401

    # Student → 403
    student = main.SESSION_STORE.create(sub="s-live-unauth", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_forbidden = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/submissions/summary"
        )
        assert r_forbidden.status_code == 403

    # Owner vs non-owner
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub="t-live-owner", name="Owner", roles=["teacher"])  # type: ignore
    other = main.SESSION_STORE.create(sub="t-live-other", name="Other", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        course_id = await _create_course(c, "Kurs Live")
        unit = await _create_unit(c, "Einheit U")
        # Not attached to course → 404
        r_404 = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/summary"
        )
        assert r_404.status_code in (403, 404)

        # Attach, then non-owner should get 403
        await _attach_unit(c, course_id, unit["id"])
        c.cookies.set(main.SESSION_COOKIE_NAME, other.session_id)
        r_non_owner = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/summary"
        )
        assert r_non_owner.status_code == 403

        # Invalid UUIDs → 400
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_bad = await c.get(
            "/api/teaching/courses/not-a-uuid/units/also-not-a-uuid/submissions/summary"
        )
        assert r_bad.status_code == 400


@pytest.mark.anyio
async def test_summary_happy_path_minimal_status_matrix_and_headers():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for live summary test")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-live-matrix", name="Owner", roles=["teacher"])  # type: ignore
    s1 = main.SESSION_STORE.create(sub="s-live-1", name="Anna", roles=["student"])  # type: ignore
    s2 = main.SESSION_STORE.create(sub="s-live-2", name="Ben", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Live Kurs")
        unit = await _create_unit(c, "Live Einheit")
        sec1 = await _create_section(c, unit["id"], "S1")
        sec2 = await _create_section(c, unit["id"], "S2")
        t1 = await _create_task(c, unit["id"], sec1["id"], "### A1")
        t2 = await _create_task(c, unit["id"], sec2["id"], "### A2")
        mod = await _attach_unit(c, cid, unit["id"])
        # Enroll students
        await _add_member(c, cid, s1.sub)
        await _add_member(c, cid, s2.sub)

        # Student 1 submits for task 1
        # Release section S1 so submissions are allowed
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_vis = await c.patch(
            f"/api/teaching/courses/{cid}/modules/{mod['id']}/sections/{sec1['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        # Switch to student and submit
        c.cookies.set(main.SESSION_COOKIE_NAME, s1.session_id)
        r_sub = await c.post(
            f"/api/learning/courses/{cid}/tasks/{t1['id']}/submissions",
            json={"kind": "text", "text_body": "Meine Lösung"},
        )
        # Submissions are now async → 202 Accepted when enqueued/pending
        assert r_sub.status_code in (202, 201, 200)

        # Owner fetches summary
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert r.headers.get("Vary") == "Origin"
        body = r.json()
        assert sorted([t["id"] for t in body["tasks"]]) == sorted([t1["id"], t2["id"]])
        assert len(body["rows"]) == 2
        # Map by student sub for easier checks
        rows = {row["student"]["sub"]: row for row in body["rows"]}
        assert rows[s1.sub]
        assert rows[s2.sub]
        # S1 has submission in t1, none in t2
        s1_cells = {c["task_id"]: c for c in rows[s1.sub]["tasks"]}
        assert s1_cells[t1["id"]]["has_submission"] is True
        assert s1_cells[t2["id"]]["has_submission"] is False
        # S2 has nothing
        s2_cells = {c["task_id"]: c for c in rows[s2.sub]["tasks"]}
        assert s2_cells[t1["id"]]["has_submission"] is False
        assert s2_cells[t2["id"]]["has_submission"] is False


@pytest.mark.anyio
async def test_summary_can_skip_student_rows():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for summary include_students test")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-live-include", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Include Kurs")
        unit = await _create_unit(c, "Include Einheit")
        await _attach_unit(c, cid, unit["id"])

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"include_students": False},
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["tasks"], list)
        assert body["rows"] == []


@pytest.mark.anyio
async def test_summary_rejects_invalid_updated_since():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for timestamp validation")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-live-invalid-ts", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Live Kurs Invalid")
        unit = await _create_unit(c, "Live Einheit Invalid")
        await _attach_unit(c, cid, unit["id"])

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"updated_since": "not-a-timestamp"},
        )
        assert r.status_code == 400
        body = r.json()
        assert body["detail"] == "invalid_timestamp"


@pytest.mark.anyio
async def test_summary_falls_back_when_helper_is_missing(monkeypatch, caplog):
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for helper fallback test")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-live-fallback-owner", name="Owner", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-live-fallback", name="Fallback", roles=["student"])  # type: ignore

    async with (await _client()) as owner_client, (await _client()) as student_client:
        owner_client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        student_client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)

        cid = await _create_course(owner_client, "Live Kurs Fallback")
        unit = await _create_unit(owner_client, "Live Einheit Fallback")
        section = await _create_section(owner_client, unit["id"], "S Fallback")
        task = await _create_task(owner_client, unit["id"], section["id"], "### Aufgabe")
        module = await _attach_unit(owner_client, cid, unit["id"])
        await _add_member(owner_client, cid, student.sub)
        # Release section so student can submit
        r_vis = await owner_client.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        # Student creates submission (before monkeypatch to avoid interfering with learning repo)
        r_sub = await student_client.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Fallback submission"},
        )
        assert r_sub.status_code in (200, 201, 202)

        original_connect = psycopg.connect

        class _CursorWrapper:
            def __init__(self, cursor):
                self._cursor = cursor

            def __enter__(self):
                self._cursor.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._cursor.__exit__(exc_type, exc, tb)

            def execute(self, query, params=None):
                if "get_unit_latest_submissions_for_owner" in query:
                    raise psy_errors.UndefinedFunction("function get_unit_latest_submissions_for_owner does not exist")
                return self._cursor.execute(query, params)

            def fetchall(self):
                return self._cursor.fetchall()

            def __getattr__(self, name):
                return getattr(self._cursor, name)

        class _ConnectionWrapper:
            def __init__(self, connection):
                self._connection = connection

            def __enter__(self):
                self._connection.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._connection.__exit__(exc_type, exc, tb)

            def cursor(self, *args, **kwargs):
                return _CursorWrapper(self._connection.cursor(*args, **kwargs))

            def close(self):
                return self._connection.close()

            def __getattr__(self, name):
                return getattr(self._connection, name)

        def _patched_connect(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            return _ConnectionWrapper(conn)

        monkeypatch.setattr(psycopg, "connect", _patched_connect)

        caplog.set_level("WARNING")
        response = await owner_client.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rows"], "expected rows despite helper failure"
        student_row = next(row for row in body["rows"] if row["student"]["sub"] == student.sub)
        assert any(cell["has_submission"] for cell in student_row["tasks"])
        assert any("fallback" in msg for msg in caplog.messages)
        assert any("get_unit_latest_submissions_for_owner" in msg for msg in caplog.messages)
