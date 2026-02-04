"""
Learning API — modular units (graph + module content)

Contract-first intent:
- Student-facing unit listings must expose `unit_type` so the SSR route can
  branch between linear vs modular units.
- Modular-only endpoints must fail clearly for linear units (400
  detail=invalid_unit_type) while keeping 404 semantics for non-membership.
"""

from __future__ import annotations

from uuid import UUID

import pytest
import httpx
from httpx import ASGITransport
import os

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    # Provide Origin for setup writes (dev = prod strict CSRF)
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    cid = r.json()["id"]
    UUID(cid)  # defensive: ensure UUID-like
    return cid


async def _create_unit(client: httpx.AsyncClient, title: str = "Unit") -> str:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    uid = r.json()["id"]
    UUID(uid)  # defensive: ensure UUID-like
    return uid


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_learning_course_units_include_unit_type():
    """Units list must include `unit_type` so SSR can branch (linear/modular)."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-units-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-mod-units-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs UnitType")
        unit_id = await _create_unit(c, "Unit Linear Default")
        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/api/learning/courses/{course_id}/units")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and items, "expected at least one unit"
        unit = items[0]["unit"]
        assert unit.get("id") == unit_id
        assert unit.get("unit_type") == "linear"


@pytest.mark.anyio
async def test_learning_modular_graph_endpoint_rejects_linear_units():
    """Modular graph endpoint must return 400 invalid_unit_type for linear units."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-graph-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-mod-graph-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Graph")
        unit_id = await _create_unit(c, "Unit Linear")
        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r.status_code == 400
        body = r.json()
        assert body.get("detail") == "invalid_unit_type"
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_modular_module_content_endpoint_rejects_linear_units():
    """Module content endpoint must return 400 invalid_unit_type for linear units."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-module-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-mod-module-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Module Content")
        unit_id = await _create_unit(c, "Unit Linear")
        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        module_id = "00000000-0000-0000-0000-000000000000"
        r = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}?include=materials,tasks")
        assert r.status_code == 400
        body = r.json()
        assert body.get("detail") == "invalid_unit_type"
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_modular_module_content_happy_path_via_graph():
    """Student can fetch graph modules and then load module content (materials/tasks)."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-happy-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-mod-happy-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Modular Happy")

        # Create a modular unit and a single module section with content.
        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})
        assert r_unit.status_code == 201
        unit_id = r_unit.json()["id"]
        UUID(unit_id)

        r_sec = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Modul 1"})
        assert r_sec.status_code == 201
        section_id = r_sec.json()["id"]
        UUID(section_id)

        r_mat = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            json={"title": "Material", "body_md": "Hallo"},
        )
        assert r_mat.status_code == 201

        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"]},
        )
        assert r_task.status_code == 201

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        # Student: discover module_id via graph, then load module content.
        c.cookies.set("gustav_session", student.session_id)
        r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph.status_code == 200
        graph = r_graph.json()
        assert isinstance(graph.get("modules"), list) and graph["modules"], "expected at least one module"
        module_id = graph["modules"][0]["id"]
        UUID(module_id)

        r_content = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}?include=materials,tasks"
        )
        assert r_content.status_code == 200
        payload = r_content.json()
        assert payload["module"]["id"] == module_id
        assert payload["module"]["unit_id"] == unit_id
        assert isinstance(payload.get("materials"), list) and len(payload["materials"]) == 1
        assert isinstance(payload.get("tasks"), list) and len(payload["tasks"]) == 1


@pytest.mark.anyio
async def test_learning_modular_graph_includes_edges():
    """Graph endpoint returns `edges` based on unit_module_edges (Option B module IDs)."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    dsn = os.getenv("DATABASE_URL") or f"postgresql://{os.getenv('APP_DB_USER','gustav_app')}:{os.getenv('APP_DB_PASSWORD','CHANGE_ME_DEV')}@{os.getenv('TEST_DB_HOST','127.0.0.1')}:{os.getenv('TEST_DB_PORT','54322')}/postgres"

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-edges-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-mod-edges-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Edges")

        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})
        assert r_unit.status_code == 201
        unit_id = r_unit.json()["id"]
        UUID(unit_id)

        r_a = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        assert r_a.status_code == 201
        sec_a = r_a.json()["id"]
        UUID(sec_a)

        r_b = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "B"})
        assert r_b.status_code == 201
        sec_b = r_b.json()["id"]
        UUID(sec_b)

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

    # Insert edge A -> B as the author (RLS).
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
        conn.commit()

    # Student sees the edge in the graph payload.
    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)
        r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph.status_code == 200
        graph = r_graph.json()
        assert {"from": mod_a, "to": mod_b} in (graph.get("edges") or [])


@pytest.mark.anyio
async def test_learning_modular_unlock_and_locked_module_returns_404_until_prereqs_done():
    """Locked modules must be hidden (404) until prerequisites are done."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    dsn = os.getenv("DATABASE_URL") or (
        f"postgresql://{os.getenv('APP_DB_USER','gustav_app')}:{os.getenv('APP_DB_PASSWORD','CHANGE_ME_DEV')}"
        f"@{os.getenv('TEST_DB_HOST','127.0.0.1')}:{os.getenv('TEST_DB_PORT','54322')}/postgres"
    )

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-lock-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-mod-lock-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Modular Lock")

        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})
        assert r_unit.status_code == 201
        unit_id = r_unit.json()["id"]
        UUID(unit_id)

        r_a = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        assert r_a.status_code == 201
        sec_a = r_a.json()["id"]
        UUID(sec_a)

        r_b = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "B"})
        assert r_b.status_code == 201
        sec_b = r_b.json()["id"]
        UUID(sec_b)

        r_task_a = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{sec_a}/tasks",
            json={"instruction_md": "Aufgabe A"},
        )
        assert r_task_a.status_code == 201
        task_a = r_task_a.json()["id"]
        UUID(task_a)

        r_task_b = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{sec_b}/tasks",
            json={"instruction_md": "Aufgabe B"},
        )
        assert r_task_b.status_code == 201
        task_b = r_task_b.json()["id"]
        UUID(task_b)

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

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

    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)

        # Before completing A, module B is locked and must be hidden.
        r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph.status_code == 200
        graph = r_graph.json()
        modules = {m["id"]: m for m in (graph.get("modules") or [])}
        assert modules[mod_a]["status"] == "open"
        assert modules[mod_b]["status"] == "locked"
        assert modules[mod_b]["prereq_required"] == 1
        assert modules[mod_b]["prereq_done"] == 0

        r_b_locked = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{mod_b}?include=tasks")
        assert r_b_locked.status_code == 404

        r_a_open = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{mod_a}?include=tasks")
        assert r_a_open.status_code == 200

        # After submitting for A, B unlocks.
        r_submit = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_a}/submissions",
            json={"kind": "text", "text_body": "ok"},
        )
        assert r_submit.status_code == 202

        r_graph2 = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph2.status_code == 200
        graph2 = r_graph2.json()
        modules2 = {m["id"]: m for m in (graph2.get("modules") or [])}
        assert modules2[mod_a]["status"] == "done"
        assert modules2[mod_b]["status"] == "open"

        r_b_open = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{mod_b}?include=tasks")
        assert r_b_open.status_code == 200
