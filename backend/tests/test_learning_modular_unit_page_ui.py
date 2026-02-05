"""
SSR (Student) — Modular unit page renders an advance organizer view.

Contract-first intent:
- `/learning/courses/{course_id}/units/{unit_id}` must branch by `unit_type`.
  - linear: existing released-sections view
  - modular: advance organizer (graph) + module content loading

This test only asserts the modular branch renders a stable graph shell marker.
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
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    cid = r.json()["id"]
    UUID(cid)
    return cid


async def _create_modular_unit(client: httpx.AsyncClient, title: str = "Unit Modular") -> str:
    r = await client.post("/api/teaching/units", json={"title": title, "unit_type": "modular"})
    assert r.status_code == 201
    uid = r.json()["id"]
    UUID(uid)
    return uid


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Modul 1") -> str:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    sid = r.json()["id"]
    UUID(sid)
    return sid


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str = "Aufgabe") -> str:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction},
    )
    assert r.status_code == 201
    tid = r.json()["id"]
    UUID(tid)
    return tid

async def _module_id_by_title(client: httpx.AsyncClient, *, unit_id: str, title: str) -> str:
    """Lookup module_id by title from the teaching graph.

    Notes:
      - Option B maps modules 1:1 to backing sections.
      - The section create endpoint returns section_id, so for tests we resolve
        module_id via the modular editor graph endpoint.
    """
    r_graph = await client.get(f"/api/teaching/units/{unit_id}/modules/graph")
    assert r_graph.status_code == 200, r_graph.text
    graph = r_graph.json()
    for m in graph.get("modules", []) if isinstance(graph, dict) else []:
        if isinstance(m, dict) and str(m.get("title") or "") == str(title):
            mid = str(m.get("id") or "")
            UUID(mid)
            return mid
    raise AssertionError(f"module_not_found:{title}")



async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_learning_modular_unit_page_renders_graph_shell():
    _require_db_or_skip()
    # Ensure DB-backed repos for the Learning routes
    import routes.learning as learning  # noqa: E402

    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-ui-1", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-mod-ui-1", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Modular UI")
        unit_id = await _create_modular_unit(c, "Unit Modular UI")
        section_id = await _create_section(c, unit_id, "Start")
        _ = await _create_task(c, unit_id, section_id, "Aufgabe 1")
        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}")
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        # Stable marker that the SSR route rendered the modular branch.
        html = r.text
        # Stable marker that the SSR route rendered the modular branch.
        assert 'data-unit-type="modular"' in html

        # Dummy-like Student Workspace skeleton (IDs must be stable for the JS glue).
        assert 'id="btn-view-overview"' in html
        assert 'id="btn-view-content"' in html
        assert 'id="open-tabs"' in html
        assert 'id="view-overview"' in html
        assert 'id="view-content"' in html
        assert 'id="graph-shell"' in html
        assert 'id="graph-layer"' in html
        assert 'id="content-root"' in html
        assert 'sticky-toolbar' in html

        # The dummy does not use a separate right-side content panel.
        assert 'student-modular-module-content' not in html

        # Workspace JS must be available globally (head is not updated by HTMX swaps).
        assert 'student_modular_workspace.js' in html

@pytest.mark.anyio
async def test_learning_modular_unit_module_fragment_404_when_locked() -> None:
    """Locked modules must fail-closed in the student fragment loader."""
    _require_db_or_skip()
    # Ensure DB-backed repos for the Learning routes
    import routes.learning as learning  # noqa: E402

    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-frag-1", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-mod-frag-1", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)

        course_id = await _create_course(c, "Kurs Modular Frag")
        unit_id = await _create_modular_unit(c, "Unit Modular Frag")

        # Create two modules via sections (Option B auto-creates modules).
        section_a = await _create_section(c, unit_id, "A")
        _ = await _create_task(c, unit_id, section_a, "Aufgabe A1")
        _ = await _create_section(c, unit_id, "B")

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        # Resolve module IDs by title and create an edge A -> B.
        mod_a = await _module_id_by_title(c, unit_id=unit_id, title="A")
        mod_b = await _module_id_by_title(c, unit_id=unit_id, title="B")

        r_edge = await c.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text

        # Ensure B requires the single prerequisite.
        r_patch = await c.patch(
            f"/api/teaching/units/{unit_id}/modules/{mod_b}",
            json={"required_prereq_count": 1},
        )
        assert r_patch.status_code == 200, r_patch.text
        assert int(r_patch.json().get("required_prereq_count") or 0) == 1

        # Student tries to load locked module content via SSR fragment endpoint.
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}/modules/{mod_b}/fragment")
        assert r.status_code == 404
        assert "Modul nicht verfügbar" in r.text

@pytest.mark.anyio
async def test_student_modular_workspace_static_js_is_served() -> None:
    """The student workspace JS must be served as a static asset."""
    async with (await _client()) as c:
        r = await c.get("/static/js/student_modular_workspace.js")
        assert r.status_code == 200
        assert "modular_workspace" in r.text or "modular-unit-page" in r.text

