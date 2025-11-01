"""
Learning API — Upload Intents Behaviour (RED)

Tests beschreiben das erwartete Verhalten für studentische Upload‑Intents.
Diese schlagen fehl, bis der Endpunkt implementiert ist (TDD: Red).
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import os


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _prepare_fixture():
    # Reuse existing teaching APIs to seed data quickly
    main.SESSION_STORE = SessionStore()  # in-memory
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        # Teacher creates course/unit/section/task and releases section
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"})
        assert r_course.status_code == 201
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        module_id = r_module.json()["id"]
        r_vis = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        # Add student to course
        r_member = await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name})  # type: ignore
        assert r_member.status_code == 201
    return student.session_id, course_id, task_id


@pytest.mark.anyio
async def test_upload_intent_image_png_happy_path():
    student_sid, course_id, task_id = await _prepare_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "foto.png", "mime_type": "image/png", "size_bytes": 2048},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body.get("storage_key") and body.get("url")
    assert "image/png" in body.get("accepted_mime_types", [])
    assert int(body.get("max_size_bytes", 0)) >= 10485760
    # Security cache header + vary
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_upload_intent_rejects_gif_and_too_large():
    student_sid, course_id, task_id = await _prepare_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r1 = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "anim.gif", "mime_type": "image/gif", "size_bytes": 1024},
            headers={"Origin": "http://test"},
        )
        r2 = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "file", "filename": "zu_gross.pdf", "mime_type": "application/pdf", "size_bytes": 20_000_000},
            headers={"Origin": "http://test"},
        )
    assert r1.status_code == 400
    assert r2.status_code == 400


@pytest.mark.anyio
async def test_upload_intent_requires_authentication():
    # No session cookie -> 401
    async with (await _client()) as c:
        r = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 401
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_upload_intent_forbidden_for_teacher():
    # Teacher role is not allowed to create student upload intents
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
        )
    assert r.status_code == 403


@pytest.mark.anyio
async def test_upload_intent_pdf_happy_path_includes_pdf_mime():
    """File kind (PDF) returns intent with accepted_mime_types including application/pdf."""
    student_sid, course_id, task_id = await _prepare_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "file", "filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 4096},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body.get("storage_key") and body.get("url")
    assert "application/pdf" in body.get("accepted_mime_types", [])


@pytest.mark.anyio
async def test_upload_intent_requires_membership():
    """Student must be course member; otherwise 403 before presign."""
    # Prepare teacher-created resources without enrolling the student
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"})
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
        )
        task_id = r_task.json()["id"]
        # Section is made visible, but student is not a member
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
        )
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 403


@pytest.mark.anyio
async def test_upload_intent_task_not_visible_returns_404():
    """If task not visible to student (section not released), respond 404."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"})
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
        )
        task_id = r_task.json()["id"]
        # Add student membership but do NOT release section
        await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name})  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_upload_intent_csrf_violation_sets_detail():
    student_sid, course_id, task_id = await _prepare_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            headers={"Origin": "https://evil.example"},
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
        )
    assert r.status_code == 403
    assert r.json().get("detail") == "csrf_violation"


@pytest.mark.anyio
async def test_upload_intent_requires_origin_or_referer_header():
    """POST without Origin/Referer must be rejected with 403 (strict CSRF)."""
    student_sid, course_id, task_id = await _prepare_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
        )
    assert r.status_code == 403
    assert r.json().get("detail") == "csrf_violation"
