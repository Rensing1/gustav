"""
Learning modular unlock parity — Learning API graph status vs DB helper.

Why:
    The Learning API graph and DB helper must expose the same unlock semantics.
    This test protects against behavior drift in either path.
"""

from __future__ import annotations

import importlib
import os

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

main = importlib.import_module("backend.web.main")

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_modular_unlock_status_matches_db_helper_for_each_module(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    try:
        import psycopg  # type: ignore
        from backend.teaching.repo_db import DBTeachingRepo
        from backend.learning.repo_db import DBLearningRepo

        assert isinstance(teaching.REPO, DBTeachingRepo)
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos (and psycopg) are required")

    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="t-mod-parity-1", name="Lehrkraft", roles=["teacher"])
    student = store.create(sub="s-mod-parity-1", name="Schueler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        # Course + modular unit with 2 phases and dependency A -> B.
        course_id = (await c.post("/api/teaching/courses", json={"title": "Parity Kurs"})).json()["id"]
        unit_id = (await c.post("/api/teaching/units", json={"title": "Parity Unit", "unit_type": "modular"})).json()["id"]
        p1 = (await c.get(f"/api/teaching/units/{unit_id}/phases")).json()[0]["id"]
        p2 = (await c.post(f"/api/teaching/units/{unit_id}/phases", json={"title": "Phase 2"})).json()["id"]
        mod_a = (await c.post(f"/api/teaching/units/{unit_id}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{unit_id}/modules", json={"title": "B", "phase_id": p2})).json()["id"]
        r_edge = await c.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text

        # Add a task to A so A is open-but-not-done; then B should remain locked.
        # We read section ids directly from DB (editor API intentionally hides them).
        with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                # DB reads in tests should respect the same RLS context as runtime.
                cur.execute("select set_config('app.current_sub', %s, true)", (teacher.sub,))
                cur.execute(
                    """
                    select id::text, section_id::text
                      from public.unit_modules
                     where unit_id = %s::uuid
                    """,
                    (unit_id,),
                )
                module_rows = cur.fetchall() or []
        section_by_module = {str(mid): str(sid) for mid, sid in module_rows}
        assert mod_a in section_by_module, f"module {mod_a} missing in unit_modules query"
        section_a = section_by_module[mod_a]

        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_a}/tasks",
            json={"instruction_md": "Bearbeite A"},
        )
        assert r_task.status_code == 201, r_task.text

        # Make the unit visible for the student in this course.
        assert (await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})).status_code == 201
        assert (await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})).status_code in (201, 204)

        # Python path (Learning API graph) status.
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph.status_code == 200, r_graph.text
        modules = r_graph.json()["modules"]
        status_by_module = {str(m["id"]): str(m.get("status") or "") for m in modules}

    # SQL path (DB helper) status.
    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student.sub,))
            for module_id, status in status_by_module.items():
                section_id = section_by_module[module_id]
                cur.execute(
                    "select public.modular_section_is_open_or_done_for_student(%s, %s::uuid, %s::uuid, %s::uuid)",
                    (student.sub, course_id, unit_id, section_id),
                )
                open_or_done = bool((cur.fetchone() or [False])[0])
                assert open_or_done == (status in {"open", "done"}), (
                    f"module={module_id} python_status={status} db_open_or_done={open_or_done}"
                )


@pytest.mark.anyio
async def test_modular_unlock_done_transition_matches_db_helper_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimal parity guard for transition after completing the prerequisite module.

    Why:
        The existing parity test covers one static snapshot. This test adds a
        tiny second checkpoint after a learner submission, so drift in "done"
        transition semantics is caught early.
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    try:
        import psycopg  # type: ignore
        from backend.teaching.repo_db import DBTeachingRepo
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos (and psycopg) are required")

    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="t-mod-parity-2", name="Lehrkraft", roles=["teacher"])
    student = store.create(sub="s-mod-parity-2", name="Schueler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course_id = (await c.post("/api/teaching/courses", json={"title": "Parity Kurs 2"})).json()["id"]
        unit_id = (await c.post("/api/teaching/units", json={"title": "Parity Unit 2", "unit_type": "modular"})).json()["id"]
        p1 = (await c.get(f"/api/teaching/units/{unit_id}/phases")).json()[0]["id"]
        p2 = (await c.post(f"/api/teaching/units/{unit_id}/phases", json={"title": "Phase 2"})).json()["id"]
        mod_a = (await c.post(f"/api/teaching/units/{unit_id}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{unit_id}/modules", json={"title": "B", "phase_id": p2})).json()["id"]
        r_edge = await c.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text

        with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (teacher.sub,))
                cur.execute(
                    """
                    select id::text, section_id::text
                      from public.unit_modules
                     where unit_id = %s::uuid
                    """,
                    (unit_id,),
                )
                module_rows = cur.fetchall() or []
        section_by_module = {str(mid): str(sid) for mid, sid in module_rows}
        section_a = section_by_module[mod_a]
        section_b = section_by_module[mod_b]

        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_a}/tasks",
            json={"instruction_md": "Bearbeite A"},
        )
        assert r_task.status_code == 201, r_task.text
        task_a = r_task.json()["id"]
        # Give module B one task so it becomes "open" (not immediately "done") after unlock.
        r_task_b = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_b}/tasks",
            json={"instruction_md": "Bearbeite B"},
        )
        assert r_task_b.status_code == 201, r_task_b.text

        assert (await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})).status_code == 201
        assert (await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})).status_code in (201, 204)

        # Checkpoint 1: before submission (A=open, B=locked)
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_graph_before = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph_before.status_code == 200, r_graph_before.text
        status_before = {str(m["id"]): str(m.get("status") or "") for m in r_graph_before.json()["modules"]}
        assert status_before.get(mod_a) == "open"
        assert status_before.get(mod_b) == "locked"

        # Submission in A should move A to done and unlock B.
        r_submit = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_a}/submissions",
            json={"kind": "text", "text_body": "ok"},
        )
        assert r_submit.status_code == 202, r_submit.text

        r_graph_after = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph_after.status_code == 200, r_graph_after.text
        status_after = {str(m["id"]): str(m.get("status") or "") for m in r_graph_after.json()["modules"]}
        assert status_after.get(mod_a) == "done"
        assert status_after.get(mod_b) == "open"

    # Parity checkpoint: SQL helper must match Python state after transition.
    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student.sub,))
            for module_id, status in status_after.items():
                section_id = section_by_module[module_id]
                cur.execute(
                    "select public.modular_section_is_open_or_done_for_student(%s, %s::uuid, %s::uuid, %s::uuid)",
                    (student.sub, course_id, unit_id, section_id),
                )
                open_or_done = bool((cur.fetchone() or [False])[0])
                assert open_or_done == (status in {"open", "done"}), (
                    f"after_submit module={module_id} python_status={status} db_open_or_done={open_or_done}"
                )
