"""
Learning API — Upload Intents Behaviour (RED)

Tests beschreiben das erwartete Verhalten für studentische Upload‑Intents.
Diese schlagen fehl, bis der Endpunkt implementiert ist (TDD: Red).
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
BACKEND_DIR = REPO_ROOT / "backend"
for path in (WEB_DIR, BACKEND_DIR, REPO_ROOT):
    if str(path) not in os.sys.path:
        os.sys.path.insert(0, str(path))

import routes.learning as learning  # type: ignore  # noqa: E402
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402
from teaching.storage import NullStorageAdapter, StorageAdapterProtocol  # type: ignore  # noqa: E402


TEST_STORAGE_BASE_URL = "https://storage.example.com"


class FakeStorageAdapter(StorageAdapterProtocol):
    """Fake adapter emitting deterministic presigned URLs for tests."""

    def __init__(self) -> None:
        self.last_presign: dict | None = None

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]) -> dict:
        self.last_presign = {
            "bucket": bucket,
            "key": key,
            "expires_in": expires_in,
            "headers": headers,
        }
        return {
            "url": f"{TEST_STORAGE_BASE_URL}/{bucket}/{key}?signature=test",
            "headers": headers,
            "method": "PUT",
            "expires_in": expires_in,
        }

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": 0, "etag": "fake-etag"}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"{TEST_STORAGE_BASE_URL}/{bucket}/{key}?download=1", "headers": {}, "method": "GET"}


@contextmanager
def _use_storage_adapter(adapter):
    """Temporarily override the learning storage adapter for a test."""
    had_attr = hasattr(learning, "STORAGE_ADAPTER")
    original = getattr(learning, "STORAGE_ADAPTER", None)
    setattr(learning, "STORAGE_ADAPTER", adapter)
    try:
        yield adapter
    finally:
        if had_attr:
            setattr(learning, "STORAGE_ADAPTER", original)
        else:
            delattr(learning, "STORAGE_ADAPTER")


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
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://test"})
        assert r_course.status_code == 201
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"}, headers={"Origin": "http://test"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"}, headers={"Origin": "http://test"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
            headers={"Origin": "http://test"},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        r_vis = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r_vis.status_code == 200
        # Add student to course
        r_member = await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name}, headers={"Origin": "http://test"})  # type: ignore
        assert r_member.status_code == 201
    return student.session_id, course_id, task_id


@pytest.mark.anyio
async def test_upload_intent_image_png_happy_path(monkeypatch):
    student_sid, course_id, task_id = await _prepare_fixture()
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS", "600")
    with _use_storage_adapter(FakeStorageAdapter()):
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
            r = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
                json={"kind": "image", "filename": "foto.png", "mime_type": "image/png", "size_bytes": 2048},
                headers={"Origin": "http://test"},
            )
    assert r.status_code == 200
    body = r.json()
    UUID(body.get("intent_id", ""))
    assert body.get("storage_key") and body.get("url")
    assert body["url"].startswith(f"{TEST_STORAGE_BASE_URL}/submissions/")
    assert body.get("headers", {}).get("Content-Type") == "image/png"
    assert body.get("accepted_mime_types") == ["image/jpeg", "image/png"]
    assert int(body.get("max_size_bytes", 0)) == 10 * 1024 * 1024
    # Security cache header + vary
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.headers.get("Vary") == "Origin"
    expires_at = body.get("expires_at", "")
    assert expires_at.endswith("Z") or expires_at.endswith("+00:00")


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
    assert r.status_code == 404


@pytest.mark.anyio
async def test_upload_intent_pdf_happy_path_includes_pdf_mime(monkeypatch):
    """File kind (PDF) returns intent with accepted_mime_types including application/pdf."""
    student_sid, course_id, task_id = await _prepare_fixture()
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS", "600")
    with _use_storage_adapter(FakeStorageAdapter()):
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
    """Student must be course member; otherwise 404 to avoid leaking existence."""
    # Prepare teacher-created resources without enrolling the student
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://test"})
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"}, headers={"Origin": "http://test"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"}, headers={"Origin": "http://test"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
            headers={"Origin": "http://test"},
        )
        task_id = r_task.json()["id"]
        # Section is made visible, but student is not a member
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_upload_intent_task_not_visible_returns_404():
    """If task not visible to student (section not released), respond 404."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://test"})
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"}, headers={"Origin": "http://test"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"}, headers={"Origin": "http://test"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
            headers={"Origin": "http://test"},
        )
        task_id = r_task.json()["id"]
        # Add student membership but do NOT release section
        await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name}, headers={"Origin": "http://test"})  # type: ignore
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


@pytest.mark.anyio
async def test_upload_intent_returns_503_when_storage_missing(monkeypatch):
    student_sid, course_id, task_id = await _prepare_fixture()
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS", "600")
    with _use_storage_adapter(NullStorageAdapter()):
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
            r = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
                json={"kind": "image", "filename": "foto.png", "mime_type": "image/png", "size_bytes": 2048},
                headers={"Origin": "http://test"},
            )
    assert r.status_code == 503
    assert r.json().get("detail") == "storage_adapter_not_configured"
