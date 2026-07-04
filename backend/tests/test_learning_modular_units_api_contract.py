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
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    # Provide Origin for setup writes (dev = prod strict CSRF)
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


def _session_store(monkeypatch: pytest.MonkeyPatch):
    return install_session_store(monkeypatch, main)


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
async def test_learning_modular_module_content_rejects_empty_include_query_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`include=` must fail with 400 invalid_include (no silent defaulting)."""
    import routes.learning as learning  # noqa: E402

    class _StubRepo:
        def list_units_for_student_course(self, *, student_sub: str, course_id: str):
            assert student_sub
            assert course_id
            return []

    monkeypatch.setattr(learning, "_get_repo", lambda: _StubRepo(), raising=True)

    store = _session_store(monkeypatch)
    student = store.create(sub="s-mod-include-empty-1", name="Schueler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/11111111-1111-1111-1111-111111111111/"
            "units/22222222-2222-2222-2222-222222222222/"
            "modules/33333333-3333-3333-3333-333333333333?include="
        )

    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "invalid_include"
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_modular_module_content_rejects_trailing_comma_in_include_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`include=materials,` must fail with 400 invalid_include."""
    import routes.learning as learning  # noqa: E402

    class _StubRepo:
        def list_units_for_student_course(self, *, student_sub: str, course_id: str):
            assert student_sub
            assert course_id
            return []

    monkeypatch.setattr(learning, "_get_repo", lambda: _StubRepo(), raising=True)

    store = _session_store(monkeypatch)
    student = store.create(sub="s-mod-include-trailing-1", name="Schueler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/11111111-1111-1111-1111-111111111111/"
            "units/22222222-2222-2222-2222-222222222222/"
            "modules/33333333-3333-3333-3333-333333333333?include=materials,"
        )

    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "invalid_include"
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_course_units_include_unit_type(monkeypatch: pytest.MonkeyPatch):
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-units-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-units-1", name="Schüler", roles=["student"])  # type: ignore

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
async def test_learning_modular_graph_endpoint_rejects_linear_units(monkeypatch: pytest.MonkeyPatch):
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-graph-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-graph-1", name="Schüler", roles=["student"])  # type: ignore

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
async def test_learning_modular_module_content_endpoint_rejects_linear_units(monkeypatch: pytest.MonkeyPatch):
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-module-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-module-1", name="Schüler", roles=["student"])  # type: ignore

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
async def test_learning_modular_module_content_happy_path_via_graph(monkeypatch: pytest.MonkeyPatch):
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-happy-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-happy-1", name="Schüler", roles=["student"])  # type: ignore

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
        assert graph["modules"][0]["materials_count"] == 1
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
        # Student payload must not expose internal storage internals.
        material = payload["materials"][0]
        assert "storage_key" not in material
        assert "sha256" not in material


@pytest.mark.anyio
async def test_learning_modular_module_content_includes_file_preview_url_for_file_materials(monkeypatch: pytest.MonkeyPatch):
    """Modular module content exposes canonical file URLs for visible file materials."""
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-file-preview-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-file-preview-1", name="Schüler", roles=["student"])  # type: ignore
    original_adapter = teaching.STORAGE_ADAPTER
    try:
        class _Adapter:
            def presign_upload(self, *, bucket, key, expires_in, headers):
                return {"url": "http://storage.local/upload", "headers": {}}

            def head_object(self, *, bucket, key):
                return {"content_length": 1024, "content_type": "application/pdf"}

            def delete_object(self, *, bucket, key):
                return None

            def presign_download(self, *, bucket, key, expires_in, disposition):
                return {"url": "http://storage.local/modular-material.pdf"}

        teaching.set_storage_adapter(_Adapter())

        async with (await _client()) as c:
            c.cookies.set("gustav_session", teacher.session_id)
            course_id = await _create_course(c, "Kurs Modular File Preview")

            r_unit = await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})
            assert r_unit.status_code == 201
            unit_id = r_unit.json()["id"]

            r_sec = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Modul 1"})
            assert r_sec.status_code == 201
            section_id = r_sec.json()["id"]

            intent_resp = await c.post(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
                json={"filename": "arbeitsblatt.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
            )
            assert intent_resp.status_code == 200
            intent = intent_resp.json()
            finalize_resp = await c.post(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
                json={"intent_id": intent["intent_id"], "title": "Arbeitsblatt PDF", "sha256": "f" * 64},
            )
            assert finalize_resp.status_code == 201

            await _attach_unit(c, course_id, unit_id)
            await _add_member(c, course_id, student.sub)

            c.cookies.set("gustav_session", student.session_id)
            r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
            assert r_graph.status_code == 200
            module_id = r_graph.json()["modules"][0]["id"]

            r_content = await c.get(
                f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}?include=materials"
            )
            assert r_content.status_code == 200
            payload = r_content.json()
            material = payload["materials"][0]
            assert material["file_url"] == (
                f"/api/learning/courses/{course_id}/materials/{material['id']}/file"
                "?disposition=inline"
            )
            assert "storage_key" not in material
    finally:
        teaching.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_learning_modular_material_file_url_streams_visible_material(monkeypatch: pytest.MonkeyPatch):
    """A modular material `file_url` must stream successfully through the canonical route."""
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-file-stream-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-file-stream-1", name="Schüler", roles=["student"])  # type: ignore
    original_adapter = teaching.STORAGE_ADAPTER
    original_learning_adapter = learning.STORAGE_ADAPTER
    try:
        class _Adapter:
            def presign_upload(self, *, bucket, key, expires_in, headers):
                return {"url": "http://storage.local/upload", "headers": {}}

            def head_object(self, *, bucket, key):
                return {"content_length": 1024, "content_type": "application/pdf"}

            def delete_object(self, *, bucket, key):
                return None

            def presign_download(self, *, bucket, key, expires_in, disposition):
                return {"url": "https://storage.local/modular-material.pdf", "headers": {"authorization": "sig"}}

        async def _fake_download(*, url, max_bytes, headers=None):  # noqa: ANN001
            assert url == "https://storage.local/modular-material.pdf"
            assert headers == {"authorization": "sig"}
            assert max_bytes >= 1024
            return b"%PDF-modular-material%"

        teaching.set_storage_adapter(_Adapter())
        learning.set_storage_adapter(_Adapter())
        monkeypatch.setattr(learning, "_download_bytes_with_limit", _fake_download)

        async with (await _client()) as c:
            c.cookies.set("gustav_session", teacher.session_id)
            course_id = await _create_course(c, "Kurs Modular File Stream")

            r_unit = await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})
            assert r_unit.status_code == 201
            unit_id = r_unit.json()["id"]

            r_sec = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Modul 1"})
            assert r_sec.status_code == 201
            section_id = r_sec.json()["id"]

            intent_resp = await c.post(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
                json={"filename": "arbeitsblatt.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
            )
            assert intent_resp.status_code == 200
            intent = intent_resp.json()
            finalize_resp = await c.post(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
                json={"intent_id": intent["intent_id"], "title": "Arbeitsblatt PDF", "sha256": "f" * 64},
            )
            assert finalize_resp.status_code == 201

            await _attach_unit(c, course_id, unit_id)
            await _add_member(c, course_id, student.sub)

            c.cookies.set("gustav_session", student.session_id)
            r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
            assert r_graph.status_code == 200
            module_id = r_graph.json()["modules"][0]["id"]

            r_content = await c.get(
                f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}?include=materials"
            )
            assert r_content.status_code == 200
            payload = r_content.json()
            material = payload["materials"][0]

            file_response = await c.get(material["file_url"], params={"disposition": "attachment"})
            assert file_response.status_code == 200, file_response.text
            assert file_response.content == b"%PDF-modular-material%"
            assert file_response.headers.get("Cache-Control") == "private, no-store"
            assert file_response.headers.get("Content-Type") == "application/pdf"
            assert "attachment" in str(file_response.headers.get("Content-Disposition") or "")
    finally:
        learning.set_storage_adapter(original_learning_adapter)
        teaching.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_learning_modular_endpoints_accept_uppercase_unit_id(monkeypatch: pytest.MonkeyPatch):
    """Valid UUID casing in unit_id must not cause false 404 on modular endpoints."""
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-uppercase-unit-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-uppercase-unit-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs UnitId Uppercase")

        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Modular", "unit_type": "modular"})
        assert r_unit.status_code == 201
        unit_id = r_unit.json()["id"]
        UUID(unit_id)

        r_sec = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Modul 1"})
        assert r_sec.status_code == 201
        section_id = r_sec.json()["id"]
        UUID(section_id)

        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"]},
        )
        assert r_task.status_code == 201

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph.status_code == 200
        modules = r_graph.json().get("modules") or []
        assert isinstance(modules, list) and modules
        module_id = modules[0]["id"]
        UUID(module_id)

        unit_id_upper = unit_id.upper()
        r_graph_upper = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id_upper}/modules/graph")
        assert r_graph_upper.status_code == 200

        r_content_upper = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit_id_upper}/modules/{module_id}?include=tasks"
        )
        assert r_content_upper.status_code == 200


@pytest.mark.anyio
async def test_learning_modular_graph_includes_edges(monkeypatch: pytest.MonkeyPatch):
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-edges-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-edges-1", name="Schüler", roles=["student"])  # type: ignore

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
async def test_learning_modular_unlock_and_locked_module_returns_404_until_prereqs_done(monkeypatch: pytest.MonkeyPatch):
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-lock-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-lock-1", name="Schüler", roles=["student"])  # type: ignore

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

        # UUID casing must not weaken fail-closed behavior for locked modules.
        r_b_locked_upper = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{mod_b.upper()}?include=tasks"
        )
        assert r_b_locked_upper.status_code == 404

        # Locked modules must also reject direct submissions (fail-closed).
        # Even if a client knows the task_id, the module is not yet accessible.
        r_submit_locked = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_b}/submissions",
            json={"kind": "text", "text_body": "should-not-work"},
        )
        assert r_submit_locked.status_code == 404

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


@pytest.mark.anyio
async def test_learning_modular_locked_task_is_hidden_in_sql_helpers(monkeypatch: pytest.MonkeyPatch):
    """Defense-in-depth: SQL helpers must hide locked modular tasks."""
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

    store = _session_store(monkeypatch)
    teacher = store.create(sub="t-mod-sql-1", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = store.create(sub="s-mod-sql-1", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Modular SQL Guards")

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

        r_task_b = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{sec_b}/tasks",
            json={"instruction_md": "Aufgabe B"},
        )
        assert r_task_b.status_code == 201
        task_b = r_task_b.json()["id"]
        UUID(task_b)

        await _attach_unit(c, course_id, unit_id)
        await _add_member(c, course_id, student.sub)

    # Configure dependency A -> B and require 1 prereq for B (B starts as locked).
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

    # Locked modular task must be hidden in SQL helpers too (not only API layer).
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student.sub,))
            cur.execute(
                "select public.check_task_visible_to_student(%s, %s::uuid, %s::uuid)",
                (student.sub, course_id, task_b),
            )
            visible = bool((cur.fetchone() or [False])[0])
            assert visible is False

            cur.execute(
                """
                select task_id::text
                from public.get_task_metadata_for_student(%s, %s::uuid, %s::uuid)
                """,
                (student.sub, course_id, task_b),
            )
            assert cur.fetchone() is None

    # Complete prerequisite task A, then B must become visible in SQL helpers.
    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)
        # Discover A task id via module A content.
        r_graph = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
        assert r_graph.status_code == 200
        graph = r_graph.json()
        modules = {m["title"]: m["id"] for m in (graph.get("modules") or [])}
        mod_a = modules.get("A")
        assert mod_a is not None
        r_mod_a = await c.get(f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{mod_a}?include=tasks")
        assert r_mod_a.status_code == 200
        tasks_a = r_mod_a.json().get("tasks") or []
        assert tasks_a, "expected at least one task in module A"
        task_a = tasks_a[0]["id"]
        r_submit_a = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_a}/submissions",
            json={"kind": "text", "text_body": "done"},
        )
        assert r_submit_a.status_code == 202

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student.sub,))
            cur.execute(
                "select public.check_task_visible_to_student(%s, %s::uuid, %s::uuid)",
                (student.sub, course_id, task_b),
            )
            visible_after = bool((cur.fetchone() or [False])[0])
            assert visible_after is True

            cur.execute(
                """
                select task_id::text
                from public.get_task_metadata_for_student(%s, %s::uuid, %s::uuid)
                """,
                (student.sub, course_id, task_b),
            )
            row_after = cur.fetchone()
            assert row_after is not None and row_after[0] == str(task_b)


@pytest.mark.anyio
async def test_learning_modular_graph_returns_503_when_repo_lacks_graph_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.routing import APIRoute  # noqa: E402

    store = _session_store(monkeypatch)
    student = store.create(sub="s-mod-guard-graph", name="S", roles=["student"])  # type: ignore

    class _RepoWithoutGraph:
        pass

    class _FakeListCourseUnitsUseCase:
        def __init__(self, _repo):  # type: ignore[no-untyped-def]
            pass

        def execute(self, _input):  # type: ignore[no-untyped-def]
            return [{"unit": {"id": "11111111-1111-1111-1111-111111111111", "unit_type": "modular"}}]

    route = next(
        r
        for r in main.app.routes
        if isinstance(r, APIRoute)
        and r.path == "/api/learning/courses/{course_id}/units/{unit_id}/modules/graph"
    )
    monkeypatch.setitem(route.endpoint.__globals__, "ListCourseUnitsUseCase", _FakeListCourseUnitsUseCase)
    monkeypatch.setitem(route.endpoint.__globals__, "ListCourseUnitsInput", lambda **kwargs: kwargs)
    monkeypatch.setitem(route.endpoint.__globals__, "_get_repo", lambda: _RepoWithoutGraph())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000001/"
            "units/11111111-1111-1111-1111-111111111111/modules/graph"
        )

    assert r.status_code == 503
    assert r.json().get("error") == "service_unavailable"
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_modular_module_content_returns_503_when_repo_lacks_content_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.routing import APIRoute  # noqa: E402

    store = _session_store(monkeypatch)
    student = store.create(sub="s-mod-guard-content", name="S", roles=["student"])  # type: ignore

    class _RepoWithoutModuleContent:
        def get_modular_unit_graph(self, **_kwargs):  # pragma: no cover - defensive
            return {}

    class _FakeListCourseUnitsUseCase:
        def __init__(self, _repo):  # type: ignore[no-untyped-def]
            pass

        def execute(self, _input):  # type: ignore[no-untyped-def]
            return [{"unit": {"id": "11111111-1111-1111-1111-111111111111", "unit_type": "modular"}}]

    route = next(
        r
        for r in main.app.routes
        if isinstance(r, APIRoute)
        and r.path == "/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}"
    )
    monkeypatch.setitem(route.endpoint.__globals__, "ListCourseUnitsUseCase", _FakeListCourseUnitsUseCase)
    monkeypatch.setitem(route.endpoint.__globals__, "ListCourseUnitsInput", lambda **kwargs: kwargs)
    monkeypatch.setitem(route.endpoint.__globals__, "_get_repo", lambda: _RepoWithoutModuleContent())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000001/"
            "units/11111111-1111-1111-1111-111111111111/"
            "modules/22222222-2222-2222-2222-222222222222?include=tasks"
        )

    assert r.status_code == 503
    assert r.json().get("error") == "service_unavailable"
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_modular_module_content_defaults_include_to_materials_and_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing include query must default to materials+tasks for deterministic clients."""
    from fastapi.routing import APIRoute  # noqa: E402

    store = _session_store(monkeypatch)
    student = store.create(sub="s-mod-include-default", name="S", roles=["student"])  # type: ignore
    observed_flags: dict[str, bool] = {}

    class _RepoWithModuleContent:
        def get_modular_module_content(self, **kwargs):  # type: ignore[no-untyped-def]
            observed_flags["materials"] = bool(kwargs.get("include_materials"))
            observed_flags["tasks"] = bool(kwargs.get("include_tasks"))
            return {
                "module": {
                    "id": kwargs["module_id"],
                    "title": "Modul A",
                    "unit_id": kwargs["unit_id"],
                    "phase_id": "33333333-3333-3333-3333-333333333333",
                    "position_in_phase": 1,
                },
                "materials": [
                    {
                        "id": "44444444-4444-4444-4444-444444444444",
                        "title": "Material A",
                        "kind": "markdown",
                    }
                ],
                "tasks": [
                    {
                        "id": "55555555-5555-5555-5555-555555555555",
                        "instruction_md": "Aufgabe A",
                        "criteria": [],
                        "kind": "native",
                    }
                ],
            }

    class _FakeListCourseUnitsUseCase:
        def __init__(self, _repo):  # type: ignore[no-untyped-def]
            pass

        def execute(self, _input):  # type: ignore[no-untyped-def]
            return [{"unit": {"id": "11111111-1111-1111-1111-111111111111", "unit_type": "modular"}}]

    route = next(
        r
        for r in main.app.routes
        if isinstance(r, APIRoute)
        and r.path == "/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}"
    )
    monkeypatch.setitem(route.endpoint.__globals__, "ListCourseUnitsUseCase", _FakeListCourseUnitsUseCase)
    monkeypatch.setitem(route.endpoint.__globals__, "ListCourseUnitsInput", lambda **kwargs: kwargs)
    monkeypatch.setitem(route.endpoint.__globals__, "_get_repo", lambda: _RepoWithModuleContent())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000001/"
            "units/11111111-1111-1111-1111-111111111111/"
            "modules/22222222-2222-2222-2222-222222222222"
        )

    assert r.status_code == 200
    assert observed_flags == {"materials": True, "tasks": True}
    body = r.json()
    assert body.get("materials")
    assert body.get("tasks")
