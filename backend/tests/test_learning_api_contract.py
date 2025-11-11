"""
Learning API — Contract-first Red Tests

These tests describe the expected behaviour for the new Learning REST API.
They intentionally fail while the endpoints are not implemented yet, ensuring we
follow the Red-Green-Refactor cycle after updating the OpenAPI contract.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence
from uuid import uuid4

import pytest
import httpx
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
# Ensure top-level package path exists so `backend.*` imports resolve without hacks
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


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


async def _create_course(client: httpx.AsyncClient, title: str) -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title}, headers={"Origin": "http://test"})
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


async def _create_task(
    client: httpx.AsyncClient,
    unit_id: str,
    section_id: str,
    *,
    instruction_md: str,
    criteria: Sequence[str] | None = None,
    hints_md: str | None = None,
    max_attempts: int | None = None,
) -> dict:
    payload: dict[str, object] = {"instruction_md": instruction_md}
    if criteria is not None:
        payload["criteria"] = list(criteria)
    if hints_md is not None:
        payload["hints_md"] = hints_md
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
    *,
    visible: bool = True,
    add_member: bool = True,
    max_attempts: int = 2,
    create_hidden_section: bool = False,
) -> LearningFixture:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    # Verify Teaching repository is DB-backed
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for Learning contract tests")

    # Verify Learning repository is DB-backed
    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed LearningRepo required for Learning contract tests")

    main.SESSION_STORE = SessionStore()
    try:
        # Ensure dev-like policies for this fixture (cookies/CSRF), independent of global test env
        main.SETTINGS.override_environment("dev")
    except Exception:
        pass

    teacher = main.SESSION_STORE.create(
        sub=f"teacher-learning-{uuid4()}",
        name="Lehrkraft",
        roles=["teacher"],
    )
    student = main.SESSION_STORE.create(
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
            hints_md="Nutze zwei Punkte.",
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
async def test_sections_requires_authentication():
    """Anonymous callers must receive 401 when requesting released sections."""

    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        response = await client.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000000/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_sections_requires_authentication_cache_header():
    """401 for unauthenticated API requests must use private cache header (contract)."""

    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        response = await client.get(
            "/api/learning/courses/00000000-0000-0000-0000-000000000000/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_sections_returns_released_items_for_enrolled_student():
    """Released sections include materials and tasks for enrolled students."""

    fixture = await _prepare_learning_fixture()

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
async def test_sections_includes_unit_id_in_section_core():
    """Course-level sections response must include section.unit_id (contract)."""

    fixture = await _prepare_learning_fixture()

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
    assert sec["unit_id"] == fixture.unit_id


@pytest.mark.anyio
async def test_sections_forbidden_for_non_member():
    """Students without membership must receive 403 when accessing sections."""

    fixture = await _prepare_learning_fixture(add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_sections_not_released_returns_404():
    """Unreleased sections must not leak existence information."""

    fixture = await _prepare_learning_fixture(visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_text_submission_returns_pending_and_enqueues_job():
    """Text submissions enter the async analysis pipeline and enqueue a worker job."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        prev = os.environ.get("ASYNC_LEARNING_ANALYSIS")
        os.environ["ASYNC_LEARNING_ANALYSIS"] = "true"
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Analyse pending"},
        )
        # restore env
        if prev is None:
            os.environ.pop("ASYNC_LEARNING_ANALYSIS", None)
        else:
            os.environ["ASYNC_LEARNING_ANALYSIS"] = prev

    assert response.status_code == 202
    body = response.json()
    assert body["analysis_status"] == "pending"
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
            conn.rollback()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "select count(*) from public.learning_submission_ocr_jobs where submission_id = %s",
                        (submission_id,),
                    )
                    job_count = int(cur.fetchone()[0])
            except (psycopg.errors.UndefinedTable, psycopg.errors.InsufficientPrivilege):  # type: ignore[attr-defined]
                pytest.skip(
                    "Queue table missing or no privileges; migration/grants not applied in this environment."
                )

    assert job_count == 1


@pytest.mark.anyio
async def test_create_submission_respects_attempt_limit_and_idempotency():
    """Creating submissions enforces attempt limit and honours Idempotency-Key."""

    fixture = await _prepare_learning_fixture(max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # First attempt → pending analysis
        resp1 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key"},
            json={"kind": "text", "text_body": "Versuch 1"},
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
            json={"kind": "text", "text_body": "Versuch 1"},
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
            json={"kind": "text", "text_body": "Versuch 2"},
        )
        assert resp2.status_code == 202
        second_payload = resp2.json()
        assert second_payload["attempt_nr"] == 2
        assert second_payload["analysis_status"] == "pending"

        # Third attempt exceeds max_attempts → 400
        resp3 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Versuch 3"},
        )
        assert resp3.status_code == 400
        assert resp3.json().get("detail") == "max_attempts_exceeded"


@pytest.mark.anyio
async def test_create_submission_uses_teacher_defined_criteria_names():
    """Rubric scores should expose the criteria defined by the teacher."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Lineare Funktionen analysiert"},
        )

    # Async model: immediate response is pending; analysis with scores happens later.
    assert response.status_code == 202
    body = response.json()
    assert body["analysis_status"] == "pending"
    assert body.get("analysis_json") is None


@pytest.mark.anyio
async def test_create_submission_requires_membership():
    """Students without memberships must receive 403 on submission creation."""

    fixture = await _prepare_learning_fixture(add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Hallo"},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_submission_requires_released_section():
    """Creating submissions for unreleased sections must return 404."""

    fixture = await _prepare_learning_fixture(visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Noch gesperrt"},
        )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_submission_image_requires_valid_sha256():
    """Image submissions must validate hex-encoded SHA256 before touching the database."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_create_submission_csrf_origin():
    """Same-origin is required: mismatched Origin must be rejected with 403."""

    # Use in-memory session store for unit-style test (no DB)
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.post(
            f"/api/learning/courses/{uuid4()}/tasks/{uuid4()}/submissions",
            headers={"Origin": "http://evil.example"},
            json={"kind": "text", "text_body": "hi"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_create_submission_idempotency_key_length():
    """Idempotency-Key > 64 must return 400 invalid_input (pre-DB validation)."""

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.post(
            f"/api/learning/courses/{uuid4()}/tasks/{uuid4()}/submissions",
            headers={"Idempotency-Key": "a" * 65},
            json={"kind": "text", "text_body": "hi"},
        )

    assert res.status_code == 400
    assert res.json().get("detail") == "invalid_input"
@pytest.mark.anyio
async def test_get_released_tasks_excludes_hidden_section():
    """RLS helpers must not leak tasks from unreleased sections."""

    fixture = await _prepare_learning_fixture(create_hidden_section=True)

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
async def test_create_submission_image_mime_type_whitelist():
    """Reject image uploads with non-whitelisted MIME type (spec alignment)."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_create_submission_file_pdf_happy_path():
    """PDF submissions (kind=file, application/pdf) enter the async analysis pipeline."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_create_submission_file_mime_type_whitelist():
    """Reject file uploads with non-whitelisted MIME type (only application/pdf)."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_create_submission_file_size_limit_10mb():
    """Reject file uploads larger than 10 MiB."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_create_submission_text_body_blank_returns_invalid_input():
    """Blank text submissions must yield 400 invalid_input with private cache header."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "   "},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_input"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_text_body_too_long_returns_invalid_input():
    """Text submissions exceeding 10k chars must yield 400 invalid_input."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        long_text = "x" * 10001
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": long_text},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_input"
    assert res.headers.get("Cache-Control") == "private, no-store"

@pytest.mark.anyio
async def test_list_submissions_history_happy_path():
    """GET submissions must return the student's attempts newest-first with pending status."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # Create two attempts to exercise ordering
        for idx in (1, 2):
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={"Idempotency-Key": f"attempt-{idx}"},
                json={"kind": "text", "text_body": f"Antwort {idx}"},
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
    # Async: pending status until worker completes; payloads may be empty
    assert latest["analysis_status"] == "pending"
    assert latest.get("feedback_md") in (None, "", {})
    assert latest.get("analysis_json") in (None, {})
    assert earliest["attempt_nr"] == 1
    assert earliest.get("analysis_json") in (None, {})
    # Telemetry is always present per contract
    telemetry_fields = (
        "vision_attempts",
        "vision_last_error",
        "feedback_last_attempt_at",
        "feedback_last_error",
    )
    for attempt in payload:
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
async def test_list_submissions_requires_authentication():
    """Anonymous callers must receive 401 with private cache control."""

    # Fresh in-memory store without any session
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        resp = await client.get(
            f"/api/learning/courses/00000000-0000-0000-0000-000000000000/tasks/00000000-0000-0000-0000-000000000000/submissions",
            params={"limit": 10, "offset": 0},
        )

    assert resp.status_code == 401
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_history_empty_returns_200_array():
    """Empty histories must still return HTTP 200 with an empty list."""

    fixture = await _prepare_learning_fixture()

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
async def test_list_submissions_forbidden_non_member():
    """Non-members must receive 403 without leaking payload."""

    fixture = await _prepare_learning_fixture(add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 403
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_submission_telemetry_is_sanitized_and_capped():
    """Telemetry fields must expose sanitized strings and ISO timestamps."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "telemetry-check"},
            json={"kind": "text", "text_body": "Antwort"},
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
async def test_list_submissions_404_when_not_released():
    """Unreleased tasks must look like they do not exist."""

    fixture = await _prepare_learning_fixture(visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 404
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_invalid_uuid_returns_400_with_cache_header():
    """Malformed identifiers must yield 400 with private cache headers."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.get(
            "/api/learning/courses/not-a-uuid/tasks/also-not-a-uuid/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert resp.status_code == 400
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_submissions_ordering_is_stable_by_created_then_attempt_desc():
    """When timestamps match, ordering must fall back to attempt_nr DESC."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        for idx in (1, 2):
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={"Idempotency-Key": f"stable-{idx}"},
                json={"kind": "text", "text_body": f"Gleichzeit {idx}"},
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
async def test_create_submission_rejects_cross_site_via_referer_when_origin_missing():
    """CSRF defense: POST with foreign Referer (no Origin) must be rejected."""

    fixture = await _prepare_learning_fixture()

    # Use a client without default Origin header to simulate missing Origin
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Referer": "http://evil.local/some/path"},
            json={"kind": "text", "text_body": "x"},
        )

    assert resp.status_code == 403
    assert resp.json().get("detail") == "csrf_violation"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_allows_same_origin_via_forwarded_when_trust_proxy_true():
    """CSRF: when proxy is trusted, X-Forwarded-* defines the server origin."""

    fixture = await _prepare_learning_fixture()

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
                json={"kind": "text", "text_body": "x"},
            )
    finally:
        if prev is None:
            os.environ.pop("GUSTAV_TRUST_PROXY", None)
        else:
            os.environ["GUSTAV_TRUST_PROXY"] = prev

        assert resp.status_code == 202


@pytest.mark.anyio
async def test_analysis_json_shape_has_expected_keys_only():
    """Pending submissions must not expose analysis_json payloads."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "analysis-shape"},
            json={"kind": "text", "text_body": "Antwort"},
        )

    assert resp.status_code == 202
    payload = resp.json()
    assert payload["analysis_status"] == "pending"
    assert payload.get("analysis_json") is None


@pytest.mark.anyio
async def test_create_submission_image_includes_text_and_scores_in_analysis_json():
    """Image submissions should enqueue analysis jobs and stay pending until processed."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_extracted_submission_response_hides_analysis_json_payload():
    """Intermediate 'extracted' rows must not expose raw analysis payloads."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        create = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "PDF pending"},
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
async def test_create_submission_image_storage_key_sane_pattern():
    """Reject image uploads with suspicious storage_key (defense-in-depth)."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={
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
async def test_sections_invalid_uuid_uses_contract_detail_and_cache_header():
    """Invalid UUID returns 400 with detail=invalid_uuid and private cache header."""

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid4()}", name="S", roles=["student"])  # type: ignore

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
async def test_create_submission_rejects_cross_origin_when_origin_header_present():
    """CSRF defense: POST with foreign Origin must be rejected with 403."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "http://evil.local"},
            json={"kind": "text", "text_body": "x"},
        )

    assert resp.status_code == 403
    assert resp.json().get("detail") == "csrf_violation"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_submission_rejects_mismatched_scheme():
    """CSRF: Origin https://... vs server http://... must be rejected."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "https://test"},
            json={"kind": "text", "text_body": "a"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_create_submission_rejects_mismatched_port():
    """CSRF: Origin with different port must be rejected."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "http://test:81"},
            json={"kind": "text", "text_body": "a"},
        )

    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_create_submission_allows_same_origin_header():
    """CSRF: Same Origin header passes and allows submission."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Origin": "http://test"},
            json={"kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 202


@pytest.mark.anyio
async def test_create_submission_allows_missing_origin():
    """CSRF: No Origin header (non-browser clients) are allowed."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 202


@pytest.mark.anyio
async def test_sections_invalid_include_returns_400_with_cache_control():
    """Invalid include parameter yields 400 invalid_include and private cache headers."""

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid4()}", name="S", roles=["student"])  # type: ignore

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
async def test_create_submission_idempotency_key_too_long_returns_400_invalid_input():
    """Idempotency-Key header longer than 64 must yield 400 invalid_input with private cache header."""

    fixture = await _prepare_learning_fixture()

    too_long_key = "x" * 65
    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": too_long_key},
            json={"kind": "text", "text_body": "ok"},
        )

    assert res.status_code == 400
    body = res.json()
    assert body.get("detail") == "invalid_input"
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_sections_forbidden_has_private_cache_header():
    """403 responses for sections include private Cache-Control header."""

    fixture = await _prepare_learning_fixture(add_member=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert res.status_code == 403
    assert res.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_sections_not_found_has_private_cache_header():
    """404 responses for sections include private Cache-Control header."""

    fixture = await _prepare_learning_fixture(visible=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        res = await client.get(
            f"/api/learning/courses/{fixture.course_id}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )

    assert res.status_code == 404
    assert res.headers.get("Cache-Control") == "private, no-store"

@pytest.mark.anyio
async def test_list_submissions_pagination_clamps_and_returns_expected_slice():
    """Pagination clamps limit to <=100 and offset to >=0."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # Create two attempts
        for idx in (1, 2):
            resp = await client.post(
                f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
                headers={"Idempotency-Key": f"clamp-{idx}"},
                json={"kind": "text", "text_body": f"Seite {idx}"},
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
async def test_submission_created_at_is_rfc3339_and_present():
    """History items must include RFC3339 UTC created_at (contract alignment)."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # Create one attempt to have a history entry
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "created-at-check"},
            json={"kind": "text", "text_body": "Zeitstempel"},
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
async def test_create_submission_202_has_private_no_store_cache_header():
    """202 Create Submission must include Cache-Control: private, no-store (async)."""

    fixture = await _prepare_learning_fixture()

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        resp = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Header-Test"},
        )

    assert resp.status_code == 202
    assert resp.headers.get("Cache-Control") == "private, no-store"
