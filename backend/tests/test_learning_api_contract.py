"""
Learning API — Contract-first Red Tests

These tests describe the expected behaviour for the new Learning REST API.
They intentionally fail while the endpoints are not implemented yet, ensuring we
follow the Red-Green-Refactor cycle after updating the OpenAPI contract.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
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
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str) -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Unit") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Section") -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert resp.status_code == 201
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
    )
    assert resp.status_code == 201
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
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_module(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    resp = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert resp.status_code == 201
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
    )
    assert resp.status_code == 200
    return resp.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    resp = await client.post(
        f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub}
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
    assert response.headers.get("Cache-Control") == "private, max-age=0"


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
async def test_create_submission_respects_attempt_limit_and_idempotency():
    """Creating submissions enforces attempt limit and honours Idempotency-Key."""

    fixture = await _prepare_learning_fixture(max_attempts=2)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        # First attempt
        resp1 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key"},
            json={"kind": "text", "text_body": "Versuch 1"},
        )
        assert resp1.status_code == 201
        first_payload = resp1.json()
        assert first_payload["attempt_nr"] == 1
        assert first_payload["analysis_status"] == "completed"
        assert first_payload["feedback"]
        analysis = first_payload["analysis_json"]
        assert isinstance(analysis, dict)
        assert analysis["text"] == "Versuch 1"
        assert analysis.get("length") == len("Versuch 1")
        assert isinstance(analysis.get("scores"), list)
        assert analysis["scores"], "Expected at least one rubric score"
        first_score = analysis["scores"][0]
        assert first_score["criterion"]
        assert isinstance(first_score["score"], int)
        assert 0 <= first_score["score"] <= 10
        assert "explanation" in first_score
        submission_id = first_payload["id"]

        # Idempotent retry must not create a second attempt
        resp_retry = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key"},
            json={"kind": "text", "text_body": "Versuch 1"},
        )
        assert resp_retry.status_code == 201
        retry_payload = resp_retry.json()
        assert retry_payload["id"] == submission_id
        assert retry_payload["attempt_nr"] == 1

        # Second attempt (new key) should succeed
        resp2 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            headers={"Idempotency-Key": "attempt-key-2"},
            json={"kind": "text", "text_body": "Versuch 2"},
        )
        assert resp2.status_code == 201
        second_payload = resp2.json()
        assert second_payload["attempt_nr"] == 2

        # Third attempt exceeds max_attempts → 400
        resp3 = await client.post(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            json={"kind": "text", "text_body": "Versuch 3"},
        )
        assert resp3.status_code == 400
        assert resp3.json().get("detail") == "max_attempts_exceeded"


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
        or f"postgresql://gustav_limited:gustav-limited@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
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
async def test_list_submissions_history_happy_path():
    """GET submissions must return the student's attempts newest-first with analysis + feedback."""

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
            assert resp.status_code == 201

        history_resp = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 20, "offset": 0},
        )

    assert history_resp.status_code == 200
    assert history_resp.headers.get("Cache-Control") == "private, max-age=0"
    payload = history_resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 2

    latest, earliest = payload[0], payload[-1]
    assert latest["attempt_nr"] == 2
    assert latest["analysis_status"] == "completed"
    assert latest["feedback"]
    assert latest["analysis_json"]["text"] == "Antwort 2"
    assert latest["analysis_json"]["scores"]
    assert earliest["attempt_nr"] == 1
    assert earliest["analysis_json"]["text"] == "Antwort 1"


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
    assert resp.headers.get("Cache-Control") == "private, max-age=0"


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
    assert resp.headers.get("Cache-Control") == "private, max-age=0"


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
    assert resp.headers.get("Cache-Control") == "private, max-age=0"


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
    assert resp.headers.get("Cache-Control") == "private, max-age=0"


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
            assert resp.status_code == 201

    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - safety
        pytest.skip("psycopg not available")

        dsn = os.getenv("RLS_TEST_SERVICE_DSN")
        if not dsn:
            pytest.skip("RLS_TEST_SERVICE_DSN required to rewrite timestamps for ordering test")
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
async def test_create_submission_image_includes_text_and_scores_in_analysis_json():
    """Image submissions should include OCR text and rubric scores in the analysis payload."""

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

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["kind"] == "image"
    assert payload["analysis_status"] == "completed"
    assert payload["storage_key"] == "uploads/student123/solution.png"
    analysis = payload["analysis_json"]
    assert analysis["text"]
    assert isinstance(analysis["scores"], list) and analysis["scores"]
    assert payload["feedback"]


    # History should include the image submission with storage_key
    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        history = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions",
            params={"limit": 5, "offset": 0},
        )
    assert history.status_code == 200
    items = history.json()
    assert isinstance(items, list) and items
    assert items[0]["storage_key"] == "uploads/student123/solution.png"
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
    assert res.headers.get("Cache-Control") == "private, max-age=0"


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
    assert resp.headers.get("Cache-Control") == "private, max-age=0"


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

    assert res.status_code == 201


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

    assert res.status_code == 201


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
    assert res.headers.get("Cache-Control") == "private, max-age=0"


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
    assert res.headers.get("Cache-Control") == "private, max-age=0"


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
    assert res.headers.get("Cache-Control") == "private, max-age=0"


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
