"""
Learning — Upload Intent returns public Supabase host in URL when configured.

Ensures dev=prod behavior: the browser-facing URL uses SUPABASE_PUBLIC_URL
instead of any internal container host.
"""
from __future__ import annotations

import importlib
import os
import uuid
import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.learning as learning  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from teaching.storage_supabase import SupabaseStorageAdapter  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


class _BucketStub:
    def create_signed_upload_url(self, path: str):
        # Internal shape missing /storage/v1, object/sign form
        return {"signed_url": f"http://supabase_kong_gustav-alpha2:8000/object/sign/submissions/{path}?sig=1"}


class _StorageStub:
    def from_(self, bucket: str):
        return _BucketStub()


class _SupabaseClientStub:
    def __init__(self):
        self.storage = _StorageStub()


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_upload_intent_uses_public_supabase_host(monkeypatch: pytest.MonkeyPatch) -> None:
    # Configure environment for public host and disable same-origin proxy
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase_kong_gustav-alpha2:8000")

    # Wire a SupabaseStorageAdapter with a stub client that yields internal URLs
    learning.set_storage_adapter(SupabaseStorageAdapter(_SupabaseClientStub()))

    # Minimal course/task owned by teacher, visible to student
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
            json={"instruction_md": "Aufgabe", "criteria": ["K"], "max_attempts": 3},
            headers={"Origin": "http://test"},
        )
        task_id = r_task.json()["id"]
        # Release section and add student
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        await c.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"sub": student.sub, "name": student.name},
            headers={"Origin": "http://test"},
        )  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 200
    data = r.json()
    from urllib.parse import urlparse
    url = data["url"]
    pu = urlparse(url)
    assert pu.scheme == "https"
    assert pu.hostname == "app.localhost"
    assert pu.path.startswith("/storage/v1/object/upload/sign/")
    assert "accepted_mime_types" in data and isinstance(data["accepted_mime_types"], list)
    assert "max_size_bytes" in data and isinstance(data["max_size_bytes"], int)
