"""
Learning API — Upload Intent response shape matches OpenAPI schema.

Asserts that the response only contains the documented fields and does not
include adapter-specific extras like `method`.
"""
from __future__ import annotations

import importlib
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
        # Deterministic URL and echo headers; include method in adapter output to
        # ensure the route does not forward it to the client response.
        return {
            "url": f"https://storage.test/{bucket}/{key}?signature=fake",
            "headers": headers,
            "method": "PUT",
            "expires_in": expires_in,
        }

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": 0}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?download=1", "headers": {}, "method": "GET"}


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_upload_intent_response_does_not_include_method(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force adapter to a fake one; ensure proxy is disabled for stable URL shape
    learning.set_storage_adapter(_FakeAdapter())
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")

    # Prepare minimal course/task visible to a student
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
            json={"instruction_md": "Aufgabe", "criteria": ["K"], "max_attempts": 3},
        )
        task_id = r_task.json()["id"]
        # Release section and add student
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
        )
        await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name})  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 200
    data = r.json()
    # Must not include method
    assert "method" not in data
    # Must include documented fields only
    expected = {"intent_id", "storage_key", "url", "headers", "accepted_mime_types", "max_size_bytes", "expires_at"}
    assert expected.issubset(set(data.keys()))

