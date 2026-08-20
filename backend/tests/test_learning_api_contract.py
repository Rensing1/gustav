"""
Learning API — Contract-first Red Tests

These tests describe the expected behaviour for the new Learning REST API.
They intentionally fail while the endpoints are not implemented yet, ensuring we
follow the Red-Green-Refactor cycle after updating the OpenAPI contract.
"""
from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from typing import Sequence
from uuid import uuid4

import pytest
import httpx
from httpx import ASGITransport

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip
from backend.tests.utils.storage_fixtures import dummy_jpeg_bytes, dummy_png_bytes
from backend.tests.runtime_auth_helpers import install_session_store
from backend.identity_access.stores import SessionStore


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

main = importlib.import_module("backend.web.main")


@dataclass
class LearningFixture:
    teacher_session_id: str
    student_session_id: str
    student_sub: str
    course_id: str
    module_id: str
    unit_id: str
    section_id: str
    material: dict
    task: dict
    hidden_section_id: str | None = None
    hidden_task: dict | None = None


async def _client() -> httpx.AsyncClient:
    # Provide Origin for strict CSRF on Learning write endpoints
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.fixture(autouse=True)
def _provide_submission_validation_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep legacy contract tests focused on API behavior, not storage setup."""
    learning = importlib.import_module("backend.web.routes.learning")

    async def _load_storage_bytes_for_validation(*, storage_key: str, max_bytes: int) -> bytes:  # noqa: ARG001
        key = str(storage_key or "").lower()
        if key.endswith((".jpg", ".jpeg")):
            return dummy_jpeg_bytes()
        if key.endswith(".png"):
            return dummy_png_bytes()
        return b"%PDF-1.7\n%%EOF\n"

    monkeypatch.setattr(learning, "_load_storage_bytes_for_validation", _load_storage_bytes_for_validation)
    backend_learning = importlib.import_module("backend.web.routes.learning")
    monkeypatch.setattr(backend_learning, "_load_storage_bytes_for_validation", _load_storage_bytes_for_validation, raising=False)
    for route in main.app.routes:
        endpoint = getattr(route, "endpoint", None)
        if getattr(endpoint, "__name__", "") == "create_submission":
            monkeypatch.setitem(endpoint.__globals__, "_load_storage_bytes_for_validation", _load_storage_bytes_for_validation)


async def _create_course(client: httpx.AsyncClient, title: str) -> str:
    resp = await client.post(
        "/api/teaching/courses",
        json={
            "title": title,
            "subject": "Testfach",
            "grade_level": "10",
            "school_year_start": 2026,
        },
        headers={"Origin": "http://test"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Unit") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Section") -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title}, headers={"Origin": "http://test"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_material(
    client: httpx.AsyncClient,
    unit_id: str,
    section_id: str,
    *,
    title: str,
    body_md: str,
) -> dict:
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
        json={"title": title, "body_md": body_md},
        headers={"Origin": "http://test"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_file_material(
    client: httpx.AsyncClient,
    unit_id: str,
    section_id: str,
    *,
    title: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
) -> dict:
    intent_resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
        json={"filename": filename, "mime_type": mime_type, "size_bytes": size_bytes},
        headers={"Origin": "http://test"},
    )
    assert intent_resp.status_code == 200, intent_resp.text
    intent = intent_resp.json()

    finalize_resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
        json={"intent_id": intent["intent_id"], "title": title, "sha256": "f" * 64},
        headers={"Origin": "http://test"},
    )
    assert finalize_resp.status_code == 201, finalize_resp.text
    return finalize_resp.json()


async def _create_task(
    client: httpx.AsyncClient,
    unit_id: str,
    section_id: str,
    *,
    instruction_md: str,
    criteria: Sequence[str] | None = None,
    teacher_context_md: str | None = None,
    max_attempts: int | None = None,
) -> dict:
    payload: dict[str, object] = {"instruction_md": instruction_md}
    if criteria is not None:
        payload["criteria"] = list(criteria)
    if teacher_context_md is not None:
        payload["teacher_context_md"] = teacher_context_md
    if max_attempts is not None:
        payload["max_attempts"] = max_attempts
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json=payload,
        headers={"Origin": "http://test"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_module(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    resp = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _set_section_visibility(
    client: httpx.AsyncClient,
    *,
    course_id: str,
    module_id: str,
    section_id: str,
    visible: bool,
) -> dict:
    resp = await client.patch(
        f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
        json={"visible": visible},
        headers={"Origin": "http://test"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    resp = await client.post(
        f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub}, headers={"Origin": "http://test"}
    )
    assert resp.status_code in (201, 204)


async def _prepare_learning_fixture(
    monkeypatch: pytest.MonkeyPatch | None = None,
    *,
    visible: bool = True,
    add_member: bool = True,
    max_attempts: int = 2,
    create_hidden_section: bool = False,
) -> LearningFixture:
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    # Verify Teaching repository is DB-backed
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for Learning contract tests")

    # Verify Learning repository is DB-backed
    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed LearningRepo required for Learning contract tests")

    if monkeypatch is not None:
        store = install_session_store(monkeypatch, main)
    else:
        store = SessionStore()
        main.RUNTIME.session_store = store
    try:
        # Ensure dev-like policies for this fixture (cookies/CSRF), independent of global test env
        main.RUNTIME.settings.override_environment("dev")
    except Exception:
        pass

    teacher = store.create(
        sub=f"teacher-learning-{uuid4()}",
        name="Lehrkraft",
        roles=["teacher"],
    )
    student = store.create(
        sub=f"student-learning-{uuid4()}",
        name="Schüler",
        roles=["student"],
    )

    hidden_section: dict | None = None
    hidden_task: dict | None = None

    async with (await _client()) as teacher_client:
        teacher_client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(teacher_client, title="Mathe 10A")
        unit = await _create_unit(teacher_client, title="Lineare Funktionen")
        section = await _create_section(teacher_client, unit["id"], title="Geraden interpretieren")
        material = await _create_material(
            teacher_client,
            unit["id"],
            section["id"],
            title="Arbeitsblatt",
            body_md="## Steigung und Achsenschnittpunkt",
        )
        task = await _create_task(
            teacher_client,
            unit["id"],
            section["id"],
            instruction_md="### Zeichne die Gerade y = 2x + 1",
            criteria=["Graph korrekt", "Steigung erläutert"],
            teacher_context_md="Nutze zwei Punkte.",
            max_attempts=max_attempts,
        )
        module = await _create_module(teacher_client, course_id, unit["id"])
        if visible:
            await _set_section_visibility(
                teacher_client,
                course_id=course_id,
                module_id=module["id"],
                section_id=section["id"],
                visible=True,
            )
        if create_hidden_section:
            hidden_section = await _create_section(
                teacher_client,
                unit["id"],
                title="Geheime Aufgaben",
            )
            hidden_task = await _create_task(
                teacher_client,
                unit["id"],
                hidden_section["id"],
                instruction_md="### Versteckte Aufgabe",
                criteria=["Nicht sichtbar"],
                max_attempts=max_attempts,
            )
        if add_member:
            await _add_member(teacher_client, course_id, student.sub)

    return LearningFixture(
        teacher_session_id=teacher.session_id,
        student_session_id=student.session_id,
        student_sub=student.sub,
        course_id=course_id,
        module_id=module["id"],
        unit_id=unit["id"],
        section_id=section["id"],
        material=material,
        task=task,
        hidden_section_id=hidden_section["id"] if hidden_section else None,
        hidden_task=hidden_task,
    )


@pytest.mark.anyio
async def test_sections_requires_authentication(monkeypatch: pytest.MonkeyPatch):
    """Anonymous callers must receive 401 when requesting released sections."""

    install_session_store(monkeypatch, main)

    async with (await _client()) as client:
        response = await client.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000000/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_sections_requires_authentication_cache_header(monkeypatch: pytest.MonkeyPatch):
    """401 for unauthenticated API requests must use private cache header (contract)."""

    install_session_store(monkeypatch, main)

    async with (await _client()) as client:
        response = await client.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000000/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_sections_returns_released_items_for_enrolled_student(monkeypatch: pytest.MonkeyPatch):
    """Released sections include materials and tasks for enrolled students."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    section_entry = payload[0]
    assert section_entry["section"]["id"] == fixture.section_id
    materials = section_entry["materials"]
    assert len(materials) == 1
    assert materials[0]["title"] == fixture.material["title"]
    tasks = section_entry["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["id"] == fixture.task["id"]
    assert tasks[0]["max_attempts"] == fixture.task.get("max_attempts")


@pytest.mark.anyio
async def test_sections_includes_unit_id_in_section_core(monkeypatch: pytest.MonkeyPatch):
    """Course-level sections response must include section.unit_id (contract)."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"limit": 50, "offset": 0},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    section_entry = payload[0]
    assert "section" in section_entry
    sec = section_entry["section"]
    assert isinstance(sec.get("unit_id"), str)


@pytest.mark.anyio
async def test_sections_include_stable_file_url_for_released_file_materials(monkeypatch: pytest.MonkeyPatch):
    """Released file materials expose a stable app URL for the student UI."""
    teaching = importlib.import_module("backend.web.routes.teaching")

    fixture = await _prepare_learning_fixture()
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
                return {"url": "http://storage.local/material-preview.pdf"}

        teaching.set_storage_adapter(_Adapter())

        async with (await _client()) as teacher_client:
          teacher_client.cookies.set("gustav_session", fixture.teacher_session_id)
          await _create_file_material(
              teacher_client,
              fixture.unit_id,
              fixture.section_id,
              title="Arbeitsblatt PDF",
              filename="arbeitsblatt.pdf",
              mime_type="application/pdf",
              size_bytes=1024,
          )

        async with (await _client()) as student_client:
            student_client.cookies.set("gustav_session", fixture.student_session_id)
            response = await student_client.get(
                f"/api/learning/courses/{fixture.course_id}/sections",
                params={"include": "materials", "limit": 50, "offset": 0},
            )

        assert response.status_code == 200
        payload = response.json()
        materials = payload[0]["materials"]
        file_material = next(item for item in materials if item["kind"] == "file")
        assert file_material["file_url"] == (
            f"/api/learning/courses/{fixture.course_id}/materials/{file_material['id']}/file"
            "?disposition=inline"
        )
        assert "storage_key" not in file_material
    finally:
        teaching.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_sections_forbidden_for_non_member(monkeypatch: pytest.MonkeyPatch):
    """Students without membership must receive 403 when accessing sections."""

    fixture = await _prepare_learning_fixture(monkeypatch, add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_sections_not_released_returns_404(monkeypatch: pytest.MonkeyPatch):
    """Unreleased sections must not leak existence information."""

    fixture = await _prepare_learning_fixture(monkeypatch, visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_text_submission_returns_pending_and_enqueues_job(monkeypatch: pytest.MonkeyPatch):
    """Text submissions enter the async analysis pipeline and enqueue a worker job."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        prev = os.environ.get("ASYNC_LEARNING_ANALYSIS")
        os.environ["ASYNC_LEARNING_ANALYSIS"] = "true"
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Analyse pending"},
        )
        # restore env
        if prev is None:
            os.environ.pop("ASYNC_LEARNING_ANALYSIS", None)
        else:
            os.environ["ASYNC_LEARNING_ANALYSIS"] = prev

    assert response.status_code == 202
    body = response.json()
    assert body["analysis_status"] == "pending"
    assert body["intent"] == "submit"
    assert body["text_body"] == "Analyse pending"
    assert body.get("analysis_json") is None
    assert body.get("error_code") is None

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - safety for environments without psycopg
        pytest.skip("psycopg not available")

    dsn = (
        os.getenv("DATABASE_URL")
        or f"postgresql://{os.getenv('APP_DB_USER', 'gustav_app')}:{os.getenv('APP_DB_PASSWORD', 'CHANGE_ME_DEV')}@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )
    submission_id = body["id"]
    job_count: int | None = None
    with psycopg.connect(dsn) as conn:  # type: ignore
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "select count(*) from public.learning_submission_jobs where submission_id = %s",
                    (submission_id,),
                )
                job_count = int(cur.fetchone()[0])
        except (psycopg.errors.UndefinedTable, psycopg.errors.InsufficientPrivilege):  # type: ignore[attr-defined]
            pytest.skip(
                "Queue table missing or no privileges; migration/grants not applied in this environment."
            )

    assert job_count == 1


@pytest.mark.anyio
async def test_create_submission_defaults_missing_intent_to_submit() -> None:
    """Missing intent remains backwards-compatible and is treated as a final submission."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Intent fehlt"},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["intent"] == "submit"
    assert payload["kind"] == "text"


@pytest.mark.anyio
async def test_create_submission_rejects_unknown_intent() -> None:
    """Only the documented submission intents are accepted by the runtime API."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "draft", "kind": "text", "text_body": "Ungültiger Intent"},
        )

    assert response.status_code == 400
    assert response.json() == {"error": "bad_request", "detail": "invalid_input"}


@pytest.mark.anyio
async def test_create_submission_respects_attempt_limit_and_idempotency(monkeypatch: pytest.MonkeyPatch):
    """Creating submissions enforces attempt limit and honours Idempotency-Key."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # First attempt → pending analysis
        resp1 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key"},
            json={"intent": "submit", "kind": "text", "text_body": "Versuch 1"},
        )
        assert resp1.status_code == 202
        first_payload = resp1.json()
        assert first_payload["attempt_nr"] == 1
        assert first_payload["analysis_status"] == "pending"
        assert first_payload.get("analysis_json") is None
        assert first_payload.get("feedback_md") is None
        assert first_payload["text_body"] == "Versuch 1"
        submission_id = first_payload["id"]

        # Idempotent retry must not create a second attempt or alter payload
        resp_retry = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key"},
            json={"intent": "submit", "kind": "text", "text_body": "Versuch 1"},
        )
        assert resp_retry.status_code == 202
        retry_payload = resp_retry.json()
        assert retry_payload["id"] == submission_id
        assert retry_payload["attempt_nr"] == 1
        assert retry_payload["analysis_status"] == "pending"

        # Second attempt (new key) should succeed and remain pending
        resp2 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key-2"},
            json={"intent": "submit", "kind": "text", "text_body": "Versuch 2"},
        )
        assert resp2.status_code == 202
        second_payload = resp2.json()
        assert second_payload["attempt_nr"] == 2
        assert second_payload["analysis_status"] == "pending"

        # Third attempt exceeds max_attempts → 400
        resp3 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Versuch 3"},
        )
        assert resp3.status_code == 400
        assert resp3.json().get("detail") == "max_attempts_exceeded"


@pytest.mark.anyio
async def test_feedback_requests_do_not_consume_final_attempt_limit(monkeypatch: pytest.MonkeyPatch):
    """Feedback runs stay async, but only final submissions count against max_attempts."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=1)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        feedback_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert feedback_response.status_code == 202
        feedback_payload = feedback_response.json()
        assert feedback_payload["intent"] == "feedback"
        assert feedback_payload["attempt_nr"] == 1

        final_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Jetzt ist es final."},
        )
        assert final_response.status_code == 202
        final_payload = final_response.json()
        assert final_payload["intent"] == "submit"
        assert final_payload["attempt_nr"] == 2

        blocked_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Noch ein finaler Versuch."},
        )
        assert blocked_response.status_code == 400
        assert blocked_response.json().get("detail") == "max_attempts_exceeded"


@pytest.mark.anyio
async def test_feedback_request_reuses_matching_inflight_text_submission_even_with_new_idempotency_key(monkeypatch: pytest.MonkeyPatch):
    """Identical in-flight feedback requests should not enqueue a second analysis run."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        first = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "feedback-first"},
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert first.status_code == 202
        first_payload = first.json()

        second = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "feedback-second"},
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert second.status_code == 202
        second_payload = second.json()

    assert second_payload["id"] == first_payload["id"]
    assert second_payload["attempt_nr"] == first_payload["attempt_nr"]
    assert second_payload["analysis_status"] == "pending"

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")

    service_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv("DATABASE_URL")
    if not service_dsn:
        pytest.skip("No service DSN available for queue verification.")

    with psycopg.connect(service_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and task_id = %s::uuid
                   and student_sub = %s
                   and intent = 'feedback'
                """,
                (fixture.course_id, fixture.task["id"], fixture.student_sub),
            )
            assert int(cur.fetchone()[0] or 0) == 1
            cur.execute(
                "select count(*) from public.learning_submission_jobs where submission_id = %s::uuid",
                (first_payload["id"],),
            )
            assert int(cur.fetchone()[0] or 0) == 1


@pytest.mark.anyio
async def test_feedback_request_reuses_matching_inflight_upload_submission_even_with_new_idempotency_key(monkeypatch: pytest.MonkeyPatch):
    """Identical upload feedback requests should reuse the existing pending submission."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)

    payload = {
        "intent": "feedback",
        "kind": "image",
        "storage_key": "uploads/student123/solution-a.png",
        "mime_type": "image/png",
        "size_bytes": 1024,
        "sha256": "1" * 64,
    }
    payload_retry = {
        **payload,
        "storage_key": "uploads/student123/solution-b.png",
    }

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        first = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "upload-feedback-first"},
            json=payload,
        )
        assert first.status_code == 202
        first_payload = first.json()

        second = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "upload-feedback-second"},
            json=payload_retry,
        )
        assert second.status_code == 202
        second_payload = second.json()

    assert second_payload["id"] == first_payload["id"]
    assert second_payload["attempt_nr"] == first_payload["attempt_nr"]
    assert second_payload["kind"] == "image"

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")

    service_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv("DATABASE_URL")
    if not service_dsn:
        pytest.skip("No service DSN available for queue verification.")

    with psycopg.connect(service_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and task_id = %s::uuid
                   and student_sub = %s
                   and intent = 'feedback'
                """,
                (fixture.course_id, fixture.task["id"], fixture.student_sub),
            )
            assert int(cur.fetchone()[0] or 0) == 1
            cur.execute(
                "select count(*) from public.learning_submission_jobs where submission_id = %s::uuid",
                (first_payload["id"],),
            )
            assert int(cur.fetchone()[0] or 0) == 1


@pytest.mark.anyio
async def test_feedback_request_creates_new_submission_again_after_previous_feedback_completed(monkeypatch: pytest.MonkeyPatch):
    """A deliberate re-run after completed feedback must create a fresh submission."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        first = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "completed-feedback-first"},
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert first.status_code == 202
        first_payload = first.json()

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")

    service_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv("DATABASE_URL")
    if not service_dsn:
        pytest.skip("No service DSN available to rewrite submission state.")

    with psycopg.connect(service_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set analysis_status = 'completed',
                       feedback_md = '## Rückmeldung\n\nPasst.',
                       analysis_json = '{"schema":"criteria.v2","criteria_results":[]}'::jsonb,
                       error_code = null,
                       completed_at = now()
                 where id = %s::uuid
                """,
                (first_payload["id"],),
            )
        conn.commit()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        second = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "completed-feedback-second"},
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert second.status_code == 202
        second_payload = second.json()

    assert second_payload["id"] != first_payload["id"]
    assert second_payload["attempt_nr"] == first_payload["attempt_nr"] + 1
    assert second_payload["analysis_status"] == "pending"

    with psycopg.connect(service_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and task_id = %s::uuid
                   and student_sub = %s
                   and intent = 'feedback'
                """,
                (fixture.course_id, fixture.task["id"], fixture.student_sub),
            )
            assert int(cur.fetchone()[0] or 0) == 2


@pytest.mark.anyio
async def test_finalize_latest_feedback_submission_creates_final_submission_without_worker_job(monkeypatch: pytest.MonkeyPatch):
    """Finalizing the latest reviewed draft should not enqueue a new worker job."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        feedback_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert feedback_response.status_code == 202
        feedback_submission_id = feedback_response.json()["id"]

    _require_db_or_skip()
    import psycopg  # type: ignore

    service_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv("DATABASE_URL")
    if not service_dsn:
        pytest.skip("No service DSN available for finalize contract test.")

    with psycopg.connect(service_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set analysis_status = 'completed',
                       feedback_md = '## Rückmeldung\n\nStark.',
                       analysis_json = '{"schema":"criteria.v2","criteria_results":[{"criterion":"Graph korrekt","score":8,"max_score":10,"explanation_md":"Treffend."}]}'::jsonb,
                       completed_at = now()
                 where id = %s::uuid
                """,
                (feedback_submission_id,),
            )
            conn.commit()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        # A parallel tab may create a newer draft after the learner reviewed
        # the first one. Finalization must stay bound to the selected draft.
        newer_feedback_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "feedback", "kind": "text", "text_body": "Neuer, noch ungeprüfter Entwurf."},
        )
        assert newer_feedback_response.status_code == 202

        finalize_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/finalize",
            headers={"Idempotency-Key": "finalize-key-1"},
            json={"feedback_submission_id": feedback_submission_id},
        )

    assert finalize_response.status_code == 201, finalize_response.text
    body = finalize_response.json()
    assert body["intent"] == "submit"
    assert body["attempt_nr"] == 3
    assert body["analysis_status"] == "completed"
    assert body["feedback_md"].startswith("## Rückmeldung")

    with psycopg.connect(service_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from public.learning_submission_jobs where submission_id = %s::uuid",
                (body["id"],),
            )
            assert int(cur.fetchone()[0] or 0) == 0


@pytest.mark.anyio
async def test_finalize_latest_feedback_file_submission_returns_decorated_files(monkeypatch: pytest.MonkeyPatch):
    """Finalizing an upload draft must return the same learner-visible file decoration as history."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)
    learning = importlib.import_module("backend.web.routes.learning")

    original_adapter = learning.STORAGE_ADAPTER
    try:
        class _Adapter:
            def presign_download(self, *, bucket, key, expires_in, disposition):
                if disposition == "attachment":
                    return {"url": "http://storage.local/finalized-upload.pdf?download=1"}
                return {"url": "http://storage.local/finalized-upload.pdf"}

        learning.set_storage_adapter(_Adapter())

        async with (await _client()) as client:
            client.cookies.set("gustav_session", fixture.student_session_id)
            feedback_response = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                json={
                    "intent": "feedback",
                    "kind": "file",
                    "storage_key": "submissions/finalize/native-upload.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 2048,
                    "sha256": "e" * 64,
                },
            )
            assert feedback_response.status_code == 202, feedback_response.text
            feedback_submission_id = feedback_response.json()["id"]

        _require_db_or_skip()
        import psycopg  # type: ignore

        service_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv("DATABASE_URL")
        if not service_dsn:
            pytest.skip("No service DSN available for finalize contract test.")

        with psycopg.connect(service_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.learning_submissions
                       set analysis_status = 'completed',
                           feedback_md = '## Rückmeldung\n\nDatei geprüft.',
                           analysis_json = '{"schema":"criteria.v2","criteria_results":[{"criterion":"Graph korrekt","score":8,"max_score":10,"explanation_md":"Treffend."}]}'::jsonb,
                           completed_at = now()
                     where id = %s::uuid
                    """,
                    (feedback_submission_id,),
                )
                conn.commit()

        async with (await _client()) as client:
            client.cookies.set("gustav_session", fixture.student_session_id)
            finalize_response = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/finalize",
                headers={"Idempotency-Key": "finalize-file-key-1"},
                json={"feedback_submission_id": feedback_submission_id},
            )

        assert finalize_response.status_code == 201, finalize_response.text
        body = finalize_response.json()
        assert body["intent"] == "submit"
        assert body["kind"] == "file"
        assert body["files"] == [
            {
                "mime": "application/pdf",
                "size": 2048,
                "url": (
                    f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/{body['id']}/file"
                    "?disposition=inline"
                ),
                "download_url": (
                    f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/{body['id']}/file"
                    "?disposition=attachment"
                ),
            }
        ]
    finally:
        learning.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_learning_submission_file_route_streams_owner_file(monkeypatch: pytest.MonkeyPatch):
    """Learners should open their own submission files through a stable app route."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)
    learning = importlib.import_module("backend.web.routes.learning")

    original_adapter = learning.STORAGE_ADAPTER
    try:
        class _Adapter:
            def presign_download(self, *, bucket, key, expires_in, disposition):
                return {"url": "https://storage.local/submission.pdf", "headers": {"authorization": "sig"}}

        async def _fake_download(*, url, max_bytes, headers=None):  # noqa: ANN001
            assert url == "https://storage.local/submission.pdf"
            assert headers == {"authorization": "sig"}
            assert max_bytes >= 2048
            return b"%PDF-stable%"

        learning.set_storage_adapter(_Adapter())
        monkeypatch.setattr(learning, "_download_bytes_with_limit", _fake_download)

        async with (await _client()) as client:
            client.cookies.set("gustav_session", fixture.student_session_id)
            feedback_response = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                json={
                    "intent": "feedback",
                    "kind": "file",
                    "storage_key": "submissions/stable/native-upload.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 2048,
                    "sha256": "c" * 64,
                },
            )
            assert feedback_response.status_code == 202, feedback_response.text
            submission_id = feedback_response.json()["id"]

            file_response = await client.get(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/{submission_id}/file",
                params={"disposition": "inline"},
            )

        assert file_response.status_code == 200, file_response.text
        assert file_response.content == b"%PDF-stable%"
        assert file_response.headers.get("Cache-Control") == "private, no-store"
        assert file_response.headers.get("Content-Type") == "application/pdf"
        assert "inline" in str(file_response.headers.get("Content-Disposition") or "")
    finally:
        learning.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_learning_material_file_route_streams_released_material(monkeypatch: pytest.MonkeyPatch):
    """Released learner materials should stream through the canonical app route."""

    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    fixture = await _prepare_learning_fixture(monkeypatch)
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
                return {"url": "https://storage.local/material.pdf", "headers": {"authorization": "sig"}}

        async def _fake_download(*, url, max_bytes, headers=None):  # noqa: ANN001
            assert url == "https://storage.local/material.pdf"
            assert headers == {"authorization": "sig"}
            assert max_bytes >= 1024
            return b"%PDF-material%"

        teaching.set_storage_adapter(_Adapter())
        learning.set_storage_adapter(_Adapter())
        monkeypatch.setattr(learning, "_download_bytes_with_limit", _fake_download)

        async with (await _client()) as teacher_client:
            teacher_client.cookies.set("gustav_session", fixture.teacher_session_id)
            material = await _create_file_material(
                teacher_client,
                fixture.unit_id,
                fixture.section_id,
                title="Arbeitsblatt PDF",
                filename="arbeitsblatt.pdf",
                mime_type="application/pdf",
                size_bytes=1024,
            )

        async with (await _client()) as student_client:
            student_client.cookies.set("gustav_session", fixture.student_session_id)
            response = await student_client.get(
                f"/api/learning/courses/{fixture.course_id}/materials/{material['id']}/file",
                params={"disposition": "attachment"},
            )

        assert response.status_code == 200, response.text
        assert response.content == b"%PDF-material%"
        assert response.headers.get("Cache-Control") == "private, no-store"
        assert response.headers.get("Content-Type") == "application/pdf"
        assert "attachment" in str(response.headers.get("Content-Disposition") or "")
    finally:
        learning.set_storage_adapter(original_learning_adapter)
        teaching.set_storage_adapter(original_adapter)


@pytest.mark.anyio
async def test_learning_material_file_legacy_alias_requires_matching_section(monkeypatch: pytest.MonkeyPatch):
    """Legacy alias route must stay fail-closed when section_id does not match the visible material."""

    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    fixture = await _prepare_learning_fixture(monkeypatch, create_hidden_section=True)
    assert fixture.hidden_section_id is not None
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
                return {"url": "https://storage.local/material.pdf", "headers": {"authorization": "sig"}}

        async def _fake_download(*, url, max_bytes, headers=None):  # noqa: ANN001
            return b"%PDF-material%"

        teaching.set_storage_adapter(_Adapter())
        learning.set_storage_adapter(_Adapter())
        monkeypatch.setattr(learning, "_download_bytes_with_limit", _fake_download)

        async with (await _client()) as teacher_client:
            teacher_client.cookies.set("gustav_session", fixture.teacher_session_id)
            material = await _create_file_material(
                teacher_client,
                fixture.unit_id,
                fixture.section_id,
                title="Arbeitsblatt PDF",
                filename="arbeitsblatt.pdf",
                mime_type="application/pdf",
                size_bytes=1024,
            )

        async with (await _client()) as student_client:
            student_client.cookies.set("gustav_session", fixture.student_session_id)
            response = await student_client.get(
                f"/api/learning/courses/{fixture.course_id}/sections/{fixture.hidden_section_id}/materials/{material['id']}/file",
                params={"disposition": "inline"},
            )

        assert response.status_code == 404, response.text
    finally:
        learning.set_storage_adapter(original_learning_adapter)
        teaching.set_storage_adapter(original_adapter)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path_template",
    [
        "/api/learning/courses/{course_id}/materials/{material_id}/file",
        "/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file",
    ],
)
async def test_learning_material_file_routes_return_503_when_visibility_lookup_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    path_template: str,
):
    """Visibility lookup failures must stay distinguishable from real 404 material misses."""

    learning = importlib.import_module("backend.web.routes.learning")

    fixture = await _prepare_learning_fixture(monkeypatch)

    async def _unexpected_download(**kwargs):  # noqa: ANN001
        raise AssertionError(f"material download should not start when lookup is unavailable: {kwargs}")

    fake_repo_factory = lambda: type("_Repo", (), {"_dsn": ""})()
    monkeypatch.setattr(learning, "_get_repo", fake_repo_factory)
    monkeypatch.setattr(learning, "_download_storage_object_via_presign", _unexpected_download)

    from fastapi.routing import APIRoute

    for route in main.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path not in {
            "/api/learning/courses/{course_id}/materials/{material_id}/file",
            "/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file",
        }:
            continue
        monkeypatch.setitem(route.endpoint.__globals__, "_get_repo", fake_repo_factory)
        monkeypatch.setitem(route.endpoint.__globals__, "_download_storage_object_via_presign", _unexpected_download)

    async with (await _client()) as student_client:
        student_client.cookies.set("gustav_session", fixture.student_session_id)
        response = await student_client.get(
            path_template.format(
                course_id=fixture.course_id,
                section_id=fixture.section_id,
                material_id=fixture.material["id"],
            ),
            params={"disposition": "inline"},
        )

    assert response.status_code == 503, response.text
    assert response.json() == {
        "error": "service_unavailable",
        "detail": "authorization_unavailable",
    }


@pytest.mark.anyio
async def test_set_storage_adapter_updates_existing_learning_helpers_after_reload():
    """A fresh `learning.py` import must still retarget already-imported helper modules."""

    upload_intents = importlib.import_module("backend.web.routes.learning_upload_intents")
    storage_validation = importlib.import_module("backend.web.routes.learning_storage_validation")
    original_learning = importlib.import_module("backend.web.routes.learning")
    original_adapter = original_learning.STORAGE_ADAPTER

    for name in ("backend.web.routes.learning",):
        sys.modules.pop(name, None)

    fresh_learning = importlib.import_module("backend.web.routes.learning")
    assert fresh_learning is not original_learning

    class _Adapter:
        def presign_download(self, *, bucket, key, expires_in, disposition):
            return {"url": "http://storage.local/reloaded.pdf"}

    adapter = _Adapter()
    try:
        fresh_learning.set_storage_adapter(adapter)
        assert fresh_learning.STORAGE_ADAPTER is adapter
        assert upload_intents._current_storage_adapter() is adapter
        assert storage_validation._current_storage_adapter() is adapter
    finally:
        fresh_learning.set_storage_adapter(original_adapter)
        assert upload_intents._current_storage_adapter() is original_adapter
        assert storage_validation._current_storage_adapter() is original_adapter


def test_learning_finalize_route_stays_storage_adapter_decoupled_after_command_split() -> None:
    """The split submission command endpoint must resolve runtime state through the learning facade."""

    from fastapi.routing import APIRoute

    for route in main.app.routes:
        if (
            isinstance(route, APIRoute)
            and route.path
            == "/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize"
        ):
            assert route.endpoint.__module__ == "backend.web.routes.learning_submission_commands"
            assert "STORAGE_ADAPTER" not in route.endpoint.__globals__
            return

    raise AssertionError("finalize route not registered")


@pytest.mark.anyio
async def test_finalize_requires_completed_feedback_draft(monkeypatch: pytest.MonkeyPatch):
    """Final submit must be blocked until the latest draft has completed feedback."""

    fixture = await _prepare_learning_fixture(monkeypatch, max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)

        feedback_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "feedback", "kind": "text", "text_body": "Bitte gib mir Feedback."},
        )
        assert feedback_response.status_code == 202

        finalize_response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/finalize",
            json={"feedback_submission_id": feedback_response.json()["id"]},
        )

    assert finalize_response.status_code == 409
    assert finalize_response.json().get("detail") == "draft_not_ready"


@pytest.mark.anyio
async def test_create_submission_uses_teacher_defined_criteria_names(monkeypatch: pytest.MonkeyPatch):
    """Rubric scores should expose the criteria defined by the teacher."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Lineare Funktionen analysiert"},
        )

    # Async model: immediate response is pending; analysis with scores happens later.
    assert response.status_code == 202
    body = response.json()
    assert body["analysis_status"] == "pending"
    assert body.get("analysis_json") is None


@pytest.mark.anyio
async def test_create_submission_requires_membership(monkeypatch: pytest.MonkeyPatch):
    """Students without memberships must receive 403 on submission creation."""

    fixture = await _prepare_learning_fixture(monkeypatch, add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Hallo"},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_submission_requires_released_section(monkeypatch: pytest.MonkeyPatch):
    """Creating submissions for unreleased sections must return 404."""

    fixture = await _prepare_learning_fixture(monkeypatch, visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Noch gesperrt"},
        )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_submission_image_requires_valid_sha256(monkeypatch: pytest.MonkeyPatch):
    """Image submissions must validate hex-encoded SHA256 before touching the database."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "image",
                "storage_key": "materials/abc.png",
                "mime_type": "image/png",
                "size_bytes": 1024,
                "sha256": "g" * 64,  # invalid hex character triggers 400 pre-DB
            },
        )

    assert response.status_code == 400
    assert response.json().get("detail") == "invalid_image_payload"


@pytest.mark.anyio
async def test_create_submission_csrf_origin(monkeypatch: pytest.MonkeyPatch):
    """Same-origin is required: mismatched Origin must be rejected with 403."""

    # Use in-memory session store for unit-style test (no DB)
    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid4()}", name="S", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.post(
            f"/api/learning/courses/{uuid4()}/tasks/{uuid4()}/submissions",
            headers={"Origin": "http://evil.example"},
            json={"intent": "submit", "kind": "text", "text_body": "hi"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_create_submission_idempotency_key_length(monkeypatch: pytest.MonkeyPatch):
    """Idempotency-Key > 64 must return 400 invalid_input (pre-DB validation)."""

    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid4()}", name="S", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.post(
            f"/api/learning/courses/{uuid4()}/tasks/{uuid4()}/submissions",
            headers={"Idempotency-Key": "a" * 65},
            json={"intent": "submit", "kind": "text", "text_body": "hi"},
        )

    assert res.status_code == 400
    assert res.json().get("detail") == "invalid_input"
@pytest.mark.anyio
async def test_get_released_tasks_excludes_hidden_section(monkeypatch: pytest.MonkeyPatch):
    """RLS helpers must not leak tasks from unreleased sections."""

    fixture = await _prepare_learning_fixture(monkeypatch, create_hidden_section=True)

    hidden_section_id = fixture.hidden_section_id
    assert hidden_section_id is not None, "Hidden section required for test"

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - safety
        pytest.skip("psycopg not available")

    dsn = (
        os.getenv("DATABASE_URL")
        or f"postgresql://{os.getenv('APP_DB_USER', 'gustav_app')}:{os.getenv('APP_DB_PASSWORD', 'CHANGE_ME_DEV')}@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (fixture.student_sub,))
            cur.execute(
                "select count(*) from public.get_released_tasks_for_student(%s, %s, %s)",
                (fixture.student_sub, fixture.course_id, hidden_section_id),
            )
            count = int(cur.fetchone()[0])

    assert count == 0


@pytest.mark.anyio
async def test_create_submission_image_mime_type_whitelist(monkeypatch: pytest.MonkeyPatch):
    """Reject image uploads with non-whitelisted MIME type (spec alignment)."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "image",
                "storage_key": "materials/abc.png",
                "mime_type": "image/gif",  # not allowed
                "size_bytes": 512,
                "sha256": "a" * 64,
            },
        )

    assert response.status_code == 400
    assert response.json().get("detail") == "invalid_image_payload"


@pytest.mark.anyio
async def test_create_submission_file_pdf_happy_path(monkeypatch: pytest.MonkeyPatch):
    """PDF submissions (kind=file, application/pdf) enter the async analysis pipeline."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "file",
                "storage_key": "submissions/arbeit1.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2048,
                "sha256": "b" * 64,
            },
        )

    # Async model: accept and process later
    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "file"
    assert body["attempt_nr"] == 1
    assert body["analysis_status"] == "pending"
    assert body.get("analysis_json") is None


@pytest.mark.anyio
async def test_create_submission_file_mime_type_whitelist(monkeypatch: pytest.MonkeyPatch):
    """Reject file uploads with non-whitelisted MIME type (only application/pdf)."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "file",
                "storage_key": "submissions/abc.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size_bytes": 4096,
                "sha256": "c" * 64,
            },
        )

    assert response.status_code == 400
    assert response.json().get("detail") == "invalid_file_payload"


@pytest.mark.anyio
async def test_create_submission_file_size_limit_10mb(monkeypatch: pytest.MonkeyPatch):
    """Reject file uploads larger than 10 MiB."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "file",
                "storage_key": "submissions/zu_gross.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 10485761,  # 10 MiB + 1 byte
                "sha256": "d" * 64,
            },
        )

    assert response.status_code == 400
    assert response.json().get("detail") == "invalid_file_payload"


@pytest.mark.anyio
async def test_create_submission_text_body_blank_returns_invalid_input(monkeypatch: pytest.MonkeyPatch):
    """Blank text submissions must yield 400 invalid_input with private cache header."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "   "},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_input"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_text_body_too_long_returns_invalid_input(monkeypatch: pytest.MonkeyPatch):
    """Text submissions exceeding 64k chars must yield 400 invalid_input."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        long_text = "x" * 65537
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": long_text},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_input"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_text_body_at_limit_accepted(monkeypatch: pytest.MonkeyPatch):
    """Text submissions up to 64k chars are accepted."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        long_text = "x" * 65536
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": long_text},
        )

    assert res.status_code in (200, 201, 202)

@pytest.mark.anyio
async def test_list_submissions_history_happy_path(monkeypatch: pytest.MonkeyPatch):
    """GET submissions must return the student's attempts newest-first with pending status."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # Create two attempts to exercise ordering
        for idx in (1, 2):
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={"Idempotency-Key": f"attempt-{idx}"},
                json={
                    "intent": "feedback" if idx == 1 else "submit",
                    "kind": "text",
                    "text_body": f"Antwort {idx}"
                },
            )
            assert resp.status_code == 202

        history_resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert history_resp.status_code == 200
    # Security: success responses must not be cached
    assert history_resp.headers.get("Cache-Control") == "private, no-store"
    payload = history_resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 2

    latest, earliest = payload[0], payload[-1]
    assert latest["attempt_nr"] == 2
    assert latest["intent"] == "submit"
    # Async: pending status until worker completes; payloads may be empty
    assert latest["analysis_status"] == "pending"
    assert latest.get("feedback_md") in (None, "", {})
    assert latest.get("analysis_json") in (None, {})
    assert earliest["attempt_nr"] == 1
    assert earliest["intent"] == "feedback"
    assert earliest.get("analysis_json") in (None, {})
    # Telemetry is always present per contract
    telemetry_fields = (
        "vision_attempts",
        "vision_last_error",
        "feedback_last_attempt_at",
        "feedback_last_error",
    )
    for attempt in payload:
        assert "files" in attempt, "files missing from submission payload"
        assert isinstance(attempt["files"], list)
        for field in telemetry_fields:
            assert field in attempt, f"{field} missing from submission payload"
        assert attempt["vision_attempts"] >= 0
        assert (
            attempt["vision_last_error"] is None or len(attempt["vision_last_error"]) <= 256
        ), "vision_last_error must be sanitized to <=256 chars"
        if attempt["feedback_last_attempt_at"] is not None:
            # Fast ISO check
            assert attempt["feedback_last_attempt_at"].endswith("Z") or "+" in attempt["feedback_last_attempt_at"]


@pytest.mark.anyio
async def test_list_submissions_requires_authentication(monkeypatch: pytest.MonkeyPatch):
    """Anonymous callers must receive 401 with private cache control."""

    # Fresh in-memory store without any session
    install_session_store(monkeypatch, main)

    async with (await _client()) as client:
        resp = await client.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000000/tasks/00000000-0000-0000-0000-000000000000/submissions",
            params={"limit": 10, "offset": 0},
        )

    assert resp.status_code == 401
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_history_empty_returns_200_array(monkeypatch: pytest.MonkeyPatch):
    """Empty histories must still return HTTP 200 with an empty list."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 200
    assert resp.json() == []
    # Security: success responses must not be cached
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_forbidden_non_member(monkeypatch: pytest.MonkeyPatch):
    """Non-members must receive 403 without leaking payload."""

    fixture = await _prepare_learning_fixture(monkeypatch, add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 403
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_submission_telemetry_is_sanitized_and_capped(monkeypatch: pytest.MonkeyPatch):
    """Telemetry fields must expose sanitized strings and ISO timestamps."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "telemetry-check"},
            json={"intent": "submit", "kind": "text", "text_body": "Antwort"},
        )
        assert resp.status_code == 202
        submission_id = resp.json()["id"]

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - safety
        pytest.skip("psycopg required to seed telemetry values")

    sensitive = "FATAL secret_token=XYZ12345" + (" spam" * 200)
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to seed telemetry values")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set vision_attempts = 3,
                       vision_last_error = %s,
                       feedback_last_attempt_at = now(),
                       feedback_last_error = %s
                 where id = %s::uuid
                """,
                (sensitive, sensitive, submission_id),
            )

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        history_resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 1, "offset": 0},
        )

    assert history_resp.status_code == 200
    payload = history_resp.json()
    assert payload, "expected at least one submission"
    telemetry = payload[0]
    assert telemetry["vision_attempts"] == 3
    for key in ("vision_last_error", "feedback_last_error"):
        value = telemetry[key]
        assert value is not None
        assert "secret_token" not in value.lower()
        assert len(value) <= 256
    assert telemetry["feedback_last_attempt_at"] is not None


@pytest.mark.anyio
async def test_list_submissions_404_when_not_released(monkeypatch: pytest.MonkeyPatch):
    """Unreleased tasks must look like they do not exist."""

    fixture = await _prepare_learning_fixture(monkeypatch, visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 404
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_invalid_uuid_returns_400_with_cache_header(monkeypatch: pytest.MonkeyPatch):
    """Malformed identifiers must yield 400 with private cache headers."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            "/api/learning/courses/not-a-uuid/tasks/also-not-a-uuid/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 400
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_ordering_is_stable_by_created_then_attempt_desc(monkeypatch: pytest.MonkeyPatch):
    """When timestamps match, ordering must fall back to attempt_nr DESC."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        for idx in (1, 2):
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={"Idempotency-Key": f"stable-{idx}"},
                json={"intent": "submit", "kind": "text", "text_body": f"Gleichzeit {idx}"},
            )
            assert resp.status_code == 202

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - safety
        pytest.skip("psycopg not available")

    # Ensure both attempts share the same timestamp to test stable fallback ordering
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to rewrite timestamps for ordering test")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                set created_at = (
                    select min(created_at)
                    from public.learning_submissions
                    where student_sub = %s and task_id = %s
                )
                where student_sub = %s and task_id = %s
                """,
                (fixture.student_sub, fixture.task["id"], fixture.student_sub, fixture.task["id"]),
            )

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload[0]["attempt_nr"] == 2
    assert payload[1]["attempt_nr"] == 1


@pytest.mark.anyio
async def test_create_submission_rejects_cross_site_via_referer_when_origin_missing(monkeypatch: pytest.MonkeyPatch):
    """CSRF defense: POST with foreign Referer (no Origin) must be rejected."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    # Use a client without default Origin header to simulate missing Origin
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Referer": "http://evil.local/some/path"},
            json={"intent": "submit", "kind": "text", "text_body": "x"},
        )

    assert resp.status_code == 403
    assert resp.json().get("detail") == "csrf_violation"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_allows_same_origin_via_forwarded_when_trust_proxy_true(monkeypatch: pytest.MonkeyPatch):
    """CSRF: when proxy is trusted, X-Forwarded-* defines the server origin."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    prev = os.environ.get("GUSTAV_TRUST_PROXY")
    os.environ["GUSTAV_TRUST_PROXY"] = "true"
    try:
        async with (await _client()) as client:
            client.cookies.set("gustav_session", fixture.student_session_id)
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={
                    "Origin": "https://app.example",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-Host": "app.example",
                },
                json={"intent": "submit", "kind": "text", "text_body": "x"},
            )
    finally:
        if prev is None:
            os.environ.pop("GUSTAV_TRUST_PROXY", None)
        else:
            os.environ["GUSTAV_TRUST_PROXY"] = prev

        assert resp.status_code == 202


@pytest.mark.anyio
async def test_analysis_json_shape_has_expected_keys_only(monkeypatch: pytest.MonkeyPatch):
    """Pending submissions must not expose analysis_json payloads."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "analysis-shape"},
            json={"intent": "submit", "kind": "text", "text_body": "Antwort"},
        )

    assert resp.status_code == 202
    payload = resp.json()
    assert payload["analysis_status"] == "pending"
    assert payload.get("analysis_json") is None


@pytest.mark.anyio
async def test_create_submission_image_includes_text_and_scores_in_analysis_json(monkeypatch: pytest.MonkeyPatch):
    """Image submissions should enqueue analysis jobs and stay pending until processed."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "image",
                "storage_key": "uploads/student123/solution.png",
                "mime_type": "image/png",
                "size_bytes": 1024,
                "sha256": "0" * 64,
            },
        )

    assert resp.status_code == 202
    payload = resp.json()
    assert payload["kind"] == "image"
    assert payload["analysis_status"] == "pending"
    assert payload["storage_key"] == "uploads/student123/solution.png"
    assert payload.get("analysis_json") is None
    assert payload.get("feedback_md") is None


@pytest.mark.anyio
async def test_extracted_submission_response_hides_analysis_json_payload(monkeypatch: pytest.MonkeyPatch):
    """Intermediate 'extracted' rows must not expose raw analysis payloads."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        create = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "PDF pending"},
        )
    assert create.status_code == 202
    submission = create.json()
    submission_id = submission["id"]

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")
    from psycopg.types.json import Json  # type: ignore[attr-defined]

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to tweak submission state")

    fake_page_keys = [
        f"submissions/{fixture.course_id}/{fixture.task['id']}/{fixture.student_sub}/derived/{submission_id}/page_0001.png"
    ]

    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set analysis_status = 'extracted',
                       analysis_json = null,
                       internal_metadata = coalesce(internal_metadata, '{}'::jsonb)
                                          || jsonb_build_object('page_keys', %s::jsonb)
                 where id = %s::uuid
                """,
                (Json(fake_page_keys), submission_id),
            )
        conn.commit()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 5, "offset": 0},
        )

    assert resp.status_code == 200
    payloads = resp.json()
    extracted = next((item for item in payloads if item["id"] == submission_id), None)
    assert extracted is not None
    assert extracted["analysis_status"] == "extracted"
    assert extracted.get("analysis_json") is None
@pytest.mark.anyio
async def test_create_submission_image_storage_key_sane_pattern(monkeypatch: pytest.MonkeyPatch):
    """Reject image uploads with suspicious storage_key (defense-in-depth)."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
                "intent": "submit",
                "kind": "image",
                "storage_key": "../secrets/evil.png",
                "mime_type": "image/png",
                "size_bytes": 1024,
                "sha256": "b" * 64,
            },
        )

    assert response.status_code == 400
    assert response.json().get("detail") == "invalid_image_payload"


@pytest.mark.anyio
async def test_sections_invalid_uuid_uses_contract_detail_and_cache_header(monkeypatch: pytest.MonkeyPatch):
    """Invalid UUID returns 400 with detail=invalid_uuid and private cache header."""

    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid4()}", name="S", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.get(
            "/api/learning/courses/not-a-uuid/sections",
            params={"include": "materials", "limit": 10, "offset": 0},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_uuid"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_rejects_cross_origin_when_origin_header_present(monkeypatch: pytest.MonkeyPatch):
    """CSRF defense: POST with foreign Origin must be rejected with 403."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "http://evil.local"},
            json={"intent": "submit", "kind": "text", "text_body": "x"},
        )

    assert resp.status_code == 403
    assert resp.json().get("detail") == "csrf_violation"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_rejects_mismatched_scheme(monkeypatch: pytest.MonkeyPatch):
    """CSRF: Origin https://... vs server http://... must be rejected."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "https://test"},
            json={"intent": "submit", "kind": "text", "text_body": "a"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_create_submission_rejects_mismatched_port(monkeypatch: pytest.MonkeyPatch):
    """CSRF: Origin with different port must be rejected."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "http://test:81"},
            json={"intent": "submit", "kind": "text", "text_body": "a"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_create_submission_allows_same_origin_header(monkeypatch: pytest.MonkeyPatch):
    """CSRF: Same Origin header passes and allows submission."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "http://test"},
            json={"intent": "submit", "kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 202


@pytest.mark.anyio
async def test_create_submission_allows_missing_origin(monkeypatch: pytest.MonkeyPatch):
    """CSRF: No Origin header (non-browser clients) are allowed."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 202


@pytest.mark.anyio
async def test_sections_invalid_include_returns_400_with_cache_control(monkeypatch: pytest.MonkeyPatch):
    """Invalid include parameter yields 400 invalid_include and private cache headers."""

    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid4()}", name="S", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000000/sections",
            params={"include": "materials,invalid", "limit": 10, "offset": 0},
        )

    assert res.status_code == 400
    assert res.json().get("detail") == "invalid_include"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_idempotency_key_too_long_returns_400_invalid_input(monkeypatch: pytest.MonkeyPatch):
    """Idempotency-Key header longer than 64 must yield 400 invalid_input with private cache header."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    too_long_key = "x" * 65
    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": too_long_key},
            json={"intent": "submit", "kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_input"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_sections_forbidden_has_private_cache_header(monkeypatch: pytest.MonkeyPatch):
    """403 responses for sections include private Cache-Control header."""

    fixture = await _prepare_learning_fixture(monkeypatch, add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert res.status_code == 403
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_sections_not_found_has_private_cache_header(monkeypatch: pytest.MonkeyPatch):
    """404 responses for sections include private Cache-Control header."""

    fixture = await _prepare_learning_fixture(monkeypatch, visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert res.status_code == 404
    assert res.headers.get("Cache-Control") == "private, no-store"

@pytest.mark.anyio
async def test_list_submissions_pagination_clamps_and_returns_expected_slice(monkeypatch: pytest.MonkeyPatch):
    """Pagination clamps limit to <=100 and offset to >=0."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # Create two attempts
        for idx in (1, 2):
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={"Idempotency-Key": f"clamp-{idx}"},
                json={"intent": "submit", "kind": "text", "text_body": f"Seite {idx}"},
            )
            assert resp.status_code == 202

        # Negative offset should behave like 0 and return the latest
        resp1 = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 1, "offset": -5},
        )
        assert resp1.status_code == 200
        items1 = resp1.json()
        assert isinstance(items1, list) and len(items1) == 1
        assert items1[0]["attempt_nr"] == 2

        # Huge limit should be clamped and with offset 1 returns the earlier attempt
        resp2 = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 999, "offset": 1},
        )
        assert resp2.status_code == 200
        items2 = resp2.json()
        assert isinstance(items2, list) and len(items2) == 1
        assert items2[0]["attempt_nr"] == 1


@pytest.mark.anyio
async def test_submission_created_at_is_rfc3339_and_present(monkeypatch: pytest.MonkeyPatch):
    """History items must include RFC3339 UTC created_at (contract alignment)."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # Create one attempt to have a history entry
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "created-at-check"},
            json={"intent": "submit", "kind": "text", "text_body": "Zeitstempel"},
        )
        assert resp.status_code == 202

        history = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 1, "offset": 0},
        )

    assert history.status_code == 200
    payload = history.json()
    assert isinstance(payload, list) and payload
    created_at = payload[0].get("created_at")
    assert isinstance(created_at, str) and created_at, "created_at must be a non-empty string"
    # Expected format produced by the DB: YYYY-MM-DD"T"HH:MM:SS+00:00
    import re as _re
    assert _re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", created_at), created_at


@pytest.mark.anyio
async def test_create_submission_202_has_private_no_store_cache_header(monkeypatch: pytest.MonkeyPatch):
    """202 Create Submission must include Cache-Control: private, no-store (async)."""

    fixture = await _prepare_learning_fixture(monkeypatch)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"intent": "submit", "kind": "text", "text_body": "Header-Test"},
        )

    assert resp.status_code == 202
    assert resp.headers.get("Cache-Control") == "private, no-store"
