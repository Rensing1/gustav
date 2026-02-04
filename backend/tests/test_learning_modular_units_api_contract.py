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
