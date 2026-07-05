"""
Teaching API — Units & Course Modules (contract-first, TDD)

These tests define the desired behaviour for managing reusable Units and their
attachment to Courses as Course Modules. Implementation must follow after the
tests (red phase), ensuring Clean Architecture with DB-backed persistence and
strict RLS.
"""
from __future__ import annotations

import os
from uuid import uuid4
import uuid
import importlib

import pytest
import httpx
from fastapi.routing import APIRoute
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

main = importlib.import_module("backend.web.main")
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


def _session_store(monkeypatch: pytest.MonkeyPatch):
    return install_session_store(monkeypatch, main)


def _endpoint_globals(path: str, method: str) -> dict:
    for route in main.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method.upper() in (route.methods or set()):
            globals_dict = getattr(route.endpoint, "__globals__", None)
            if isinstance(globals_dict, dict):
                return globals_dict
    raise AssertionError(f"Route not registered: {method.upper()} {path}")


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Funktionen", summary: str | None = None) -> dict:
    payload = {"title": title}
    if summary is not None:
        payload["summary"] = summary
    resp = await client.post("/api/teaching/units", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Abschnitt") -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str = "Aufgabe") -> dict:
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction, "criteria": ["Kriterium 1"]},
    )
    assert resp.status_code == 201
    return resp.json()


def _service_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv(
        "DATABASE_URL"
    ) or f"postgresql://{user}:{password}@{host}:{port}/postgres"


class _RecordingDeleteStorage:
    def __init__(self, *, fail_on_key: str | None = None) -> None:
        self.fail_on_key = fail_on_key
        self.delete_calls: list[dict[str, str]] = []

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.delete_calls.append({"bucket": bucket, "key": key})
        if self.fail_on_key and key == self.fail_on_key:
            raise RuntimeError("storage_delete_failed")


@pytest.mark.anyio
async def test_units_require_auth_and_teacher_role(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)

    async with (await _client()) as client:
        # Unauthenticated → 401
        resp_unauth = await client.get("/api/teaching/units")
        assert resp_unauth.status_code == 401

    # Set up student session
    student = store.create(sub="student-101", name="Max", roles=["student"])
    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        resp_role = await client.post("/api/teaching/units", json={"title": "Forbidden"})
        assert resp_role.status_code == 403


@pytest.mark.anyio
async def test_teacher_can_crud_units_and_ownership_is_enforced(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher_a = store.create(sub="teacher-A", name="Frau A", roles=["teacher"])
    teacher_b = store.create(sub="teacher-B", name="Herr B", roles=["teacher"])

    async with (await _client()) as client:
        # Teacher A creates a unit
        client.cookies.set("gustav_session", teacher_a.session_id)
        created = await _create_unit(client, title="Lineare Funktionen", summary="Einführung in Steigung")
        unit_id = created["id"]
        assert created["author_id"] == "teacher-A"

        # Teacher A lists units → sees own
        lst_a = await client.get("/api/teaching/units")
        assert lst_a.status_code == 200
        assert any(u["id"] == unit_id for u in lst_a.json())

        # Teacher B should not see A's unit
        client.cookies.set("gustav_session", teacher_b.session_id)
        lst_b = await client.get("/api/teaching/units")
        assert lst_b.status_code == 200
        assert all(u["author_id"] == "teacher-B" for u in lst_b.json())

        # Teacher B cannot update or delete A's unit
        update_forbidden = await client.patch(f"/api/teaching/units/{unit_id}", json={"title": "Verboten"})
        assert update_forbidden.status_code == 403
        delete_forbidden = await client.delete(f"/api/teaching/units/{unit_id}")
        assert delete_forbidden.status_code == 403

        # Switch back to teacher A for update
        client.cookies.set("gustav_session", teacher_a.session_id)
        patched = await client.patch(
            f"/api/teaching/units/{unit_id}",
            json={"title": "Lineare Funktionen I", "summary": "Aktualisiert"},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Lineare Funktionen I"
        assert patched.json()["summary"] == "Aktualisiert"

        # Delete succeeds for the author
        deleted = await client.delete(f"/api/teaching/units/{unit_id}")
        assert deleted.status_code == 204
        assert deleted.text == ""

        # Unit no longer appears
        lst_after = await client.get("/api/teaching/units")
        assert all(u["id"] != unit_id for u in lst_after.json())


@pytest.mark.anyio
async def test_unit_validation_errors(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-validate", name="Frau V", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)

        # Missing title → 400
        resp_missing = await client.post("/api/teaching/units", json={})
        assert resp_missing.status_code == 400
        assert resp_missing.json().get("detail") == "invalid_title"

        # Too long title → 400
        resp_long = await client.post("/api/teaching/units", json={"title": "x" * 201})
        assert resp_long.status_code == 400
        assert resp_long.json().get("detail") == "invalid_title"

        # Invalid unit_type → 400
        resp_invalid_type = await client.post(
            "/api/teaching/units",
            json={"title": "Valid", "unit_type": "unknown"},
        )
        assert resp_invalid_type.status_code == 400
        assert resp_invalid_type.json().get("detail") == "invalid_unit_type"

        # Patch without fields → 400
        created = await _create_unit(client, title="Valid Unit")
        resp_empty_patch = await client.patch(f"/api/teaching/units/{created['id']}", json={})
        assert resp_empty_patch.status_code == 400
        assert resp_empty_patch.json().get("detail") == "empty_payload"


@pytest.mark.anyio
async def test_course_modules_owner_workflow_and_duplicates(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher_a = store.create(sub="teacher-mod", name="Frau Module", roles=["teacher"])
    teacher_b = store.create(sub="teacher-other", name="Herr Fremd", roles=["teacher"])

    async with (await _client()) as client:
        # Teacher A course + unit
        client.cookies.set("gustav_session", teacher_a.session_id)
        course_id = await _create_course(client, title="Mathe 10A")
        unit = await _create_unit(client, title="Quadratische Funktionen")

        # Add module → position 1
        create_module = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"], "context_notes": "Vorbereitung"},
        )
        assert create_module.status_code == 201
        body = create_module.json()
        assert body["course_id"] == course_id
        assert body["unit_id"] == unit["id"]
        assert body["position"] == 1

        # List modules sorted by position
        lst = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert lst.status_code == 200
        arr = lst.json()
        assert len(arr) == 1
        assert arr[0]["position"] == 1

        # Duplicate add → 409
        dup = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"], "context_notes": None},
        )
        assert dup.status_code == 409

        # Non-owner cannot list/add
        client.cookies.set("gustav_session", teacher_b.session_id)
        resp_list_forbidden = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert resp_list_forbidden.status_code == 403
        resp_add_forbidden = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"]},
        )
        assert resp_add_forbidden.status_code == 403


@pytest.mark.anyio
async def test_course_modules_require_unit_author(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher_a = store.create(sub="teacher-owner", name="Owner", roles=["teacher"])
    teacher_b = store.create(sub="teacher-author", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        # Teacher B creates a unit
        client.cookies.set("gustav_session", teacher_b.session_id)
        foreign_unit = await _create_unit(client, title="Fremde Einheit")

        # Teacher A creates a course
        client.cookies.set("gustav_session", teacher_a.session_id)
        course_id = await _create_course(client, title="Physik 9B")

        # Teacher A cannot attach unit authored by B
        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": foreign_unit["id"]},
        )
        assert resp.status_code == 403


@pytest.mark.anyio
async def test_course_modules_reorder_updates_positions(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-reorder", name="ReOrder", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Chemie 8")
        unit_a = await _create_unit(client, title="Laborregeln")
        unit_b = await _create_unit(client, title="Atombau")
        unit_c = await _create_unit(client, title="Periodensystem")

        # Add modules in natural order
        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()
        mod_c = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_c["id"]})).json()

        reorder = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_c["id"], mod_a["id"], mod_b["id"]]},
        )
        assert reorder.status_code == 200
        ordered = reorder.json()
        assert [m["id"] for m in ordered] == [mod_c["id"], mod_a["id"], mod_b["id"]]
        assert [m["position"] for m in ordered] == [1, 2, 3]

        # GET reflects new order
        lst = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert [m["id"] for m in lst.json()] == [mod_c["id"], mod_a["id"], mod_b["id"]]


@pytest.mark.anyio
async def test_course_modules_reorder_validation_rules(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-validate-mod", name="ValidMod", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Geschichte 7")
        unit_a = await _create_unit(client, title="Mittelalter")
        unit_b = await _create_unit(client, title="Neuzeit")

        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()

        # Duplicate IDs → 400
        dup = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"], mod_a["id"]]},
        )
        assert dup.status_code == 400
        assert dup.json().get("detail") == "duplicate_module_ids"

        # Missing ID → 400
        missing = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"]]},
        )
        assert missing.status_code == 400
        assert missing.json().get("detail") == "module_mismatch"

        # Extraneous ID → 400
        extra = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"], str(uuid4()), mod_b["id"]]},
        )
        assert extra.status_code == 400
        assert extra.json().get("detail") == "module_mismatch"

        # Module from another course → 404
        other_course = await _create_course(client, title="Geschichte Parallel")
        mod_other = (
            await client.post(f"/api/teaching/courses/{other_course}/modules", json={"unit_id": unit_a["id"]})
        ).json()
        cross = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"], mod_b["id"], mod_other["id"]]},
        )
        assert cross.status_code == 404


@pytest.mark.anyio
async def test_deleting_unit_cascades_course_modules(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-delete", name="Delete", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Informatik 11")
        unit = await _create_unit(client, title="Algorithmen")

        mod_resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"]},
        )
        assert mod_resp.status_code == 201

        # Delete unit → expect cascade (no modules remain)
        del_unit = await client.delete(f"/api/teaching/units/{unit['id']}")
        assert del_unit.status_code == 204

        modules_after = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert modules_after.status_code == 200
        assert modules_after.json() == []


@pytest.mark.anyio
async def test_deleting_unit_keeps_unit_when_storage_cleanup_fails(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    teaching = importlib.import_module("backend.web.routes.teaching")

    original_repo = teaching.REPO
    original_storage = teaching.STORAGE_ADAPTER
    original_override = teaching._STORAGE_ADAPTER_OVERRIDE_ACTIVE
    repo = teaching._Repo()
    teaching.set_repo(repo)
    teaching.set_storage_adapter(_RecordingDeleteStorage(fail_on_key="unit/delete/file.pdf"))

    def collect_storage_objects(repo_arg: object, *, unit_id: str) -> list[tuple[str, str]]:
        return [("submissions", "unit/delete/file.pdf")]

    monkeypatch.setitem(
        _endpoint_globals("/api/teaching/units/{unit_id}", "DELETE"),
        "_collect_unit_delete_storage_objects",
        collect_storage_objects,
    )

    teacher = store.create(sub="teacher-storage-abort", name="Storage Abort", roles=["teacher"])

    try:
        async with (await _client()) as client:
            client.cookies.set("gustav_session", teacher.session_id)
            unit = await _create_unit(client, title="Nicht löschen")

            deleted = await client.delete(f"/api/teaching/units/{unit['id']}")
            assert deleted.status_code == 502
            assert deleted.json()["detail"] == "storage_delete_failed"

            still_there = await client.get(f"/api/teaching/units/{unit['id']}")
            assert still_there.status_code == 200
    finally:
        teaching.set_repo(original_repo)
        teaching.set_storage_adapter(original_storage, override=original_override)


@pytest.mark.anyio
async def test_deleting_unit_removes_material_and_submission_storage_objects(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    import psycopg  # type: ignore  # noqa: E402

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    storage = _RecordingDeleteStorage()
    original_adapter = teaching.STORAGE_ADAPTER
    teaching.set_storage_adapter(storage)
    teacher = store.create(sub="teacher-unit-storage-delete", name="Storage Delete", roles=["teacher"])
    learner = store.create(sub="learner-unit-storage-delete", name="Learner", roles=["student"])

    try:
        async with (await _client()) as client:
            client.cookies.set("gustav_session", teacher.session_id)
            course_id = await _create_course(client, title="Storage Kurs")
            unit = await _create_unit(client, title="Storage Einheit")
            section = await _create_section(client, unit["id"], "Materialien")
            task = await _create_task(client, unit["id"], section["id"], "Datei bearbeiten")
            module = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit["id"]})
            assert module.status_code == 201

            material_storage_key = f"materials/{unit['id']}/{section['id']}/{uuid.uuid4()}/file.pdf"
            submission_storage_key = f"submissions/{course_id}/{task['id']}/{learner.sub}/orig/answer.pdf"
            derived_storage_key = f"submissions/{course_id}/{task['id']}/{learner.sub}/derived/{uuid.uuid4()}/page_0001.png"

            with psycopg.connect(_service_dsn()) as conn:
                with conn.cursor() as cur:
                    cur.execute("select set_config('app.current_sub', %s, false)", (teacher.sub,))
                    cur.execute(
                        """
                        insert into public.unit_materials (
                          unit_id, section_id, title, body_md, kind, storage_key,
                          filename_original, mime_type, size_bytes, sha256, position
                        ) values (
                          %s::uuid, %s::uuid, 'Arbeitsblatt', '', 'file', %s,
                          'arbeitsblatt.pdf', 'application/pdf', 1024, %s, 1
                        )
                        """,
                        (unit["id"], section["id"], material_storage_key, "a" * 64),
                    )
                    cur.execute(
                        """
                        insert into public.learning_submissions (
                          id, course_id, task_id, section_id, student_sub, kind,
                          storage_key, mime_type, size_bytes, sha256, attempt_nr,
                          analysis_status, internal_metadata, completed_at
                        ) values (
                          %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                          %s, 'application/pdf', 2048, %s, 1,
                          'extracted', jsonb_build_object('page_keys', jsonb_build_array(%s::text)), now()
                        )
                        """,
                        (
                            str(uuid.uuid4()),
                            course_id,
                            task["id"],
                            section["id"],
                            learner.sub,
                            submission_storage_key,
                            "b" * 64,
                            derived_storage_key,
                        ),
                    )
                conn.commit()

            response = await client.delete(f"/api/teaching/units/{unit['id']}")

            assert response.status_code == 204
            assert {"bucket": teaching.MATERIAL_FILE_SETTINGS.storage_bucket, "key": material_storage_key} in storage.delete_calls
            assert {"bucket": teaching.get_submissions_bucket(), "key": submission_storage_key} in storage.delete_calls
            assert {"bucket": teaching.get_submissions_bucket(), "key": derived_storage_key} in storage.delete_calls
    finally:
        teaching.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_deleting_unit_aborts_when_storage_delete_fails(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    import psycopg  # type: ignore  # noqa: E402

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-unit-storage-fail", name="Storage Fail", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Bleibt erhalten")
        section = await _create_section(client, unit["id"], "Materialien")
        failing_key = f"materials/{unit['id']}/{section['id']}/{uuid.uuid4()}/file.pdf"

        with psycopg.connect(_service_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, false)", (teacher.sub,))
                cur.execute(
                    """
                    insert into public.unit_materials (
                      unit_id, section_id, title, body_md, kind, storage_key,
                      filename_original, mime_type, size_bytes, sha256, position
                    ) values (
                      %s::uuid, %s::uuid, 'Arbeitsblatt', '', 'file', %s,
                      'arbeitsblatt.pdf', 'application/pdf', 1024, %s, 1
                    )
                    """,
                    (unit["id"], section["id"], failing_key, "c" * 64),
                )
            conn.commit()

        storage = _RecordingDeleteStorage(fail_on_key=failing_key)
        original_adapter = teaching.STORAGE_ADAPTER
        teaching.set_storage_adapter(storage)
        try:
            response = await client.delete(f"/api/teaching/units/{unit['id']}")
        finally:
            teaching.set_storage_adapter(original_adapter)

        assert response.status_code == 502
        assert response.json().get("detail") == "storage_delete_failed"
        still_there = await client.get(f"/api/teaching/units/{unit['id']}")
        assert still_there.status_code == 200


@pytest.mark.anyio
async def test_course_modules_reorder_with_invalid_uuid_returns_400(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-invalid-reorder", name="Invalid", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Biologie 8")
        unit_a = await _create_unit(client, title="Zellen")
        unit_b = await _create_unit(client, title="Genetik")

        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()

        payload = {"module_ids": [mod_a["id"], "not-a-uuid", mod_b["id"]]}
        resp = await client.post(f"/api/teaching/courses/{course_id}/modules/reorder", json=payload)
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_module_ids"


@pytest.mark.anyio
async def test_course_module_create_with_invalid_unit_uuid_returns_400(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-invalid-create", name="InvalidUnit", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Musik 7")

        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": "definitely-not-a-uuid"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_unit_id"


@pytest.mark.anyio
async def test_course_modules_reorder_empty_list_returns_400(monkeypatch: pytest.MonkeyPatch):
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-empty-reorder", name="Empty", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Informatik 9")
        unit_a = await _create_unit(client, title="Programmierung I")
        unit_b = await _create_unit(client, title="Programmierung II")

        _ = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        _ = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()

        # Empty array should be a 400 (not FastAPI 422)
        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": []},
        )
        assert resp.status_code == 400
        assert resp.json().get("detail") == "empty_reorder"


@pytest.mark.anyio
async def test_course_modules_reorder_invalid_course_id_returns_400(monkeypatch: pytest.MonkeyPatch):
    """Invalid course_id (not UUID) must map to 400 invalid_course_id per contract."""
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-bad-course", name="BadCourse", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        # The payload shape is otherwise fine; only path param is invalid
        resp = await client.post(
            "/api/teaching/courses/not-a-uuid/modules/reorder",
            json={"module_ids": [str(uuid4())]},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_course_id"


@pytest.mark.anyio
async def test_course_modules_reorder_non_owner_invalid_payload_is_403(monkeypatch: pytest.MonkeyPatch):
    """Non-owner should get 403 even with invalid payload (security-first, avoid error oracle)."""
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = store.create(sub="owner-guard", name="Owner", roles=["teacher"])
    other = store.create(sub="other-guard", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        # Owner creates a course
        client.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(client, title="Security")

        # Non-owner attempts reorder with invalid payload (empty list)
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": []},
        )
        assert resp.status_code in (403, 404)
        # We accept 403 or 404 based on helper semantics, but not 400
        assert resp.status_code != 400


@pytest.mark.anyio
async def test_course_modules_delete_resequences_positions(monkeypatch: pytest.MonkeyPatch):
    """Deleting a module resequences remaining positions to 1..n (owner only)."""
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-del-mod", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Mathe 9")
        unit_a = await _create_unit(client, title="A")
        unit_b = await _create_unit(client, title="B")
        unit_c = await _create_unit(client, title="C")

        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()
        _mod_c = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_c["id"]})).json()

        # Delete middle module (B)
        resp_del = await client.delete(f"/api/teaching/courses/{course_id}/modules/{mod_b['id']}")
        assert resp_del.status_code == 204

        # Remaining modules are A and C with positions 1 and 2
        after = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert after.status_code == 200
        items = after.json()
        assert [m["position"] for m in items] == [1, 2]
        unit_ids = [m["unit_id"] for m in items]
        assert unit_a["id"] in unit_ids and unit_b["id"] not in unit_ids and unit_c["id"] in unit_ids


@pytest.mark.anyio
async def test_course_modules_delete_invalid_ids_returns_400(monkeypatch: pytest.MonkeyPatch):
    """Invalid UUIDs map to 400 with invalid_* detail (contract)."""
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-del-bad", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Biologie 7")
        unit = await _create_unit(client, title="DNA")
        mod = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit["id"]})).json()

        # Invalid module uuid → 400 invalid_module_id
        bad_mod = await client.delete(f"/api/teaching/courses/{course_id}/modules/not-a-uuid")
        assert bad_mod.status_code == 400
        assert bad_mod.json().get("detail") == "invalid_module_id"

        # Invalid course uuid → 400 invalid_course_id
        bad_course = await client.delete(f"/api/teaching/courses/not-a-uuid/modules/{mod['id']}")
        assert bad_course.status_code == 400
        assert bad_course.json().get("detail") == "invalid_course_id"


@pytest.mark.anyio
async def test_course_modules_delete_non_owner_is_403_or_404(monkeypatch: pytest.MonkeyPatch):
    """Non-owner receives 403/404 for delete to avoid error oracle (not 400)."""
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = store.create(sub="owner-del", name="Owner", roles=["teacher"])
    other = store.create(sub="other-del", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(client, title="Security Del")
        unit = await _create_unit(client, title="Auth")
        mod = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit["id"]})).json()

        client.cookies.set("gustav_session", other.session_id)
        resp = await client.delete(f"/api/teaching/courses/{course_id}/modules/{mod['id']}")
        assert resp.status_code in (403, 404)
        assert resp.status_code != 400


@pytest.mark.anyio
async def test_sections_reorder_non_author_invalid_payload_is_403(monkeypatch: pytest.MonkeyPatch):
    """Non-author should get 403/404 even with invalid payload (avoid error oracle for sections)."""
    store = _session_store(monkeypatch)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = store.create(sub="author-sec", name="Author", roles=["teacher"])
    other = store.create(sub="other-sec", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        # Author creates a unit
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Sicherheit")

        # Non-author attempts reorder with invalid payload (empty list)
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": []},
        )
        assert resp.status_code in (403, 404)
        assert resp.status_code != 400
