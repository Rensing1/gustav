"""
Learning upload-intents should honor the centralized config limit.

TDD: Ensure the `max_size_bytes` in the upload-intent response reflects the
environment-driven limit from `backend.storage.config.get_learning_max_upload_bytes`.
"""
from __future__ import annotations

import os
import uuid
import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.learning as learning  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from teaching.storage import StorageAdapterProtocol  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


class _FakeAdapter(StorageAdapterProtocol):
    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?signature=fake", "headers": headers}

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": None}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?download=1", "headers": {}}


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_learning_upload_intent_uses_config_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force a distinct config value and disable proxy for stable URL shape
    monkeypatch.setenv("LEARNING_MAX_UPLOAD_BYTES", str(3 * 1024 * 1024))  # 3 MiB
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")

    # Wire the fake storage adapter
    learning.set_storage_adapter(_FakeAdapter())

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
    body = r.json()
    assert int(body.get("max_size_bytes", 0)) == 3 * 1024 * 1024

