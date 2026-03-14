"""
SSR (Student) — Modular unit page renders an advance organizer view.

Contract-first intent:
- `/learning/courses/{course_id}/units/{unit_id}` must branch by `unit_type`.
  - linear: existing released-sections view
  - modular: advance organizer (graph) + module content loading

This test only asserts the modular branch renders a stable graph shell marker.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID
import types

import pytest
import httpx
from httpx import ASGITransport
from starlette.requests import Request
from starlette.routing import Mount

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
async def test_learning_modular_unit_module_fragment_accepts_student_in_roles_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSR modular fragment must treat `roles=['student']` as student access.

    Why:
        Learning API endpoints already accept both `role=="student"` and a
        `roles` list containing `student`. The SSR fragment route should keep
        this behavior consistent.
    """

    class _DummyResponse:
        status_code = 404

        def json(self) -> dict:
            return {}

    class _DummyClient:
        def __init__(self) -> None:
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def get(self, *args, **kwargs):  # noqa: ANN002, ANN003 - test double
            return _DummyResponse()

    class _DummyClientCtx:
        async def __aenter__(self):
            return _DummyClient()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    monkeypatch.setattr(main, "_internal_api_client", lambda: _DummyClientCtx())

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/learning/courses/00000000-0000-0000-0000-000000000001/units/00000000-0000-0000-0000-000000000002/modules/00000000-0000-0000-0000-000000000003/fragment",
        "headers": [],
        "query_string": b"",
        "state": {},
        "client": ("test", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    starlette_request = Request(scope)
    starlette_request.state.user = {"sub": "s-frag-fallback", "roles": ["student"]}

    # The internal API returns 404 in this test-double setup.
    # A 403 here would indicate the route ignored the `roles` fallback.
    response = await main.learning_modular_unit_module_fragment(
        starlette_request,
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
    )
    assert response.status_code == 404
    body = response.body.decode("utf-8")
    assert "Modul nicht verfügbar" in body


@pytest.mark.anyio
async def test_learning_modular_unit_module_fragment_renders_file_preview_when_material_is_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File materials in modular fragments must render inline preview markup."""

    course_id = "00000000-0000-0000-0000-000000000001"
    unit_id = "00000000-0000-0000-0000-000000000002"
    module_id = "00000000-0000-0000-0000-000000000003"
    section_id = "00000000-0000-0000-0000-000000000004"
    material_id = "00000000-0000-0000-0000-000000000005"

    class _DummyResponse:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _DummyClient:
        def __init__(self) -> None:
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def get(self, url: str, *args, **kwargs):  # noqa: ANN002, ANN003 - test double
            if url.endswith(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}"):
                return _DummyResponse(
                    200,
                    {
                        "module": {"id": module_id, "title": "M"},
                        "materials": [
                            {
                                "id": material_id,
                                "title": "Arbeitsblatt",
                                "kind": "file",
                                "mime_type": "application/pdf",
                                "filename_original": "blatt.pdf",
                            }
                        ],
                        "tasks": [],
                    },
                )
            if url.endswith(f"/api/learning/courses/{course_id}/units/{unit_id}/sections"):
                return _DummyResponse(
                    200,
                    [
                        {
                            "section": {"id": section_id},
                            "materials": [{"id": material_id}],
                            "tasks": [],
                        }
                    ],
                )
            return _DummyResponse(404, {"error": "not_found"})

    class _DummyClientCtx:
        async def __aenter__(self):
            return _DummyClient()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    seen: dict[str, str] = {}

    def _fake_resolve(**kwargs):  # noqa: ANN003 - test helper
        seen["section_id"] = str(kwargs.get("section_id") or "")
        seen["material_id"] = str(kwargs.get("material_id") or "")
        return "https://files.test/material.pdf"

    monkeypatch.setattr(main, "_internal_api_client", lambda: _DummyClientCtx(), raising=True)
    monkeypatch.setattr(main, "_resolve_student_material_file_url", _fake_resolve, raising=True)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment",
        "headers": [(b"cookie", b"gustav_session=session-file-frag")],
        "query_string": b"",
        "state": {},
        "client": ("test", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    starlette_request = Request(scope)
    starlette_request.state.user = {"sub": "s-file-frag", "roles": ["student"]}

    response = await main.learning_modular_unit_module_fragment(starlette_request, course_id, unit_id, module_id)
    assert response.status_code == 200
    body = response.body.decode("utf-8")
    assert 'data-file-preview="true"' in body
    assert "file-preview--pdf" in body
    assert seen == {"section_id": section_id, "material_id": material_id}


@pytest.mark.anyio
async def test_learning_modular_unit_module_fragment_uses_modular_preview_fallback_without_section_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modular file previews must still render when no linear section map is available."""

    course_id = "00000000-0000-0000-0000-000000000011"
    unit_id = "00000000-0000-0000-0000-000000000012"
    module_id = "00000000-0000-0000-0000-000000000013"
    material_id = "00000000-0000-0000-0000-000000000014"

    class _DummyResponse:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _DummyClient:
        def __init__(self) -> None:
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def get(self, url: str, *args, **kwargs):  # noqa: ANN002, ANN003 - test double
            if url.endswith(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}"):
                return _DummyResponse(
                    200,
                    {
                        "module": {"id": module_id, "title": "M"},
                        "materials": [
                            {
                                "id": material_id,
                                "title": "Arbeitsblatt",
                                "kind": "file",
                                "mime_type": "application/pdf",
                                "filename_original": "blatt.pdf",
                            }
                        ],
                        "tasks": [],
                    },
                )
            if url.endswith(f"/api/learning/courses/{course_id}/units/{unit_id}/sections"):
                return _DummyResponse(404, {"error": "not_found"})
            return _DummyResponse(404, {"error": "not_found"})

    class _DummyClientCtx:
        async def __aenter__(self):
            return _DummyClient()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    seen: dict[str, str] = {}

    def _fake_linear_resolve(**kwargs):  # noqa: ANN003 - test helper
        seen["linear_material_id"] = str(kwargs.get("material_id") or "")
        return None

    def _fake_modular_resolve(**kwargs):  # noqa: ANN003 - test helper
        seen["module_id"] = str(kwargs.get("module_id") or "")
        seen["material_id"] = str(kwargs.get("material_id") or "")
        return "https://files.test/modular-material.pdf"

    monkeypatch.setattr(main, "_internal_api_client", lambda: _DummyClientCtx(), raising=True)
    monkeypatch.setattr(main, "_resolve_student_material_file_url", _fake_linear_resolve, raising=True)
    monkeypatch.setattr(main, "_resolve_student_modular_material_file_url", _fake_modular_resolve, raising=True)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment",
        "headers": [(b"cookie", b"gustav_session=session-file-frag-modular")],
        "query_string": b"",
        "state": {},
        "client": ("test", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    starlette_request = Request(scope)
    starlette_request.state.user = {"sub": "s-file-frag-modular", "roles": ["student"]}

    response = await main.learning_modular_unit_module_fragment(starlette_request, course_id, unit_id, module_id)
    assert response.status_code == 200
    body = response.body.decode("utf-8")
    assert 'data-file-preview="true"' in body
    assert "file-preview--pdf" in body
    assert seen == {"material_id": material_id, "module_id": module_id}


@pytest.mark.anyio
async def test_student_modular_workspace_static_js_is_served() -> None:
    """Static mount must include the student modular workspace JS asset."""
    static_dir: Path | None = None
    for route in main.app.routes:
        if isinstance(route, Mount) and route.path == "/static":
            directory = getattr(getattr(route, "app", None), "directory", None)
            if isinstance(directory, str) and directory:
                static_dir = Path(directory)
                break

    assert static_dir is not None, "static_mount_missing"
    asset = static_dir / "js" / "student_modular_workspace.js"
    assert asset.is_file(), "student_modular_workspace_js_missing"

    text = asset.read_text(encoding="utf-8")
    assert "modular_workspace" in text or "modular-unit-page" in text


@pytest.mark.anyio
async def test_student_modular_workspace_static_js_served_via_auth_only_app() -> None:
    """Auth-only app must expose /static mount including the modular workspace JS."""
    app = main.create_app_auth_only()  # type: ignore[attr-defined]
    static_dir: Path | None = None
    for route in app.routes:
        if isinstance(route, Mount) and route.path == "/static":
            directory = getattr(getattr(route, "app", None), "directory", None)
            if isinstance(directory, str) and directory:
                static_dir = Path(directory)
                break

    assert static_dir is not None, "auth_only_static_mount_missing"
    asset = static_dir / "js" / "student_modular_workspace.js"
    assert asset.is_file(), "auth_only_student_modular_workspace_js_missing"
    text = asset.read_text(encoding="utf-8")
    assert "modular_workspace" in text or "modular-unit-page" in text


@pytest.mark.anyio
async def test_learning_modular_module_fragment_does_not_repeat_module_title_heading() -> None:
    """Module fragments should not repeat the module title visually.

    The module title is already present in the module card `<summary>` in the
    content view. Rendering another `<h3>{title}</h3>` inside the fragment
    duplicates the title and creates confusing UI for students.
    """
    _require_db_or_skip()
    import routes.learning as learning  # noqa: E402

    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-frag-2", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-mod-frag-2", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)

        course_id = await _create_course(c, "Kurs Modular Frag Title")
        unit_id = await _create_modular_unit(c, "Unit Modular Frag Title")

        module_title = "Einstieg"
        section_id = await _create_section(c, unit_id, module_title)
        _ = await _create_task(c, unit_id, section_id, "Aufgabe 1")

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        # Resolve module id and load fragment as student.
        module_id = await _module_id_by_title(c, unit_id=unit_id, title=module_title)
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment")
        assert r.status_code == 200

        # Guard: do not render a second visible module title heading.
        assert f"<h3>{module_title}</h3>" not in r.text
