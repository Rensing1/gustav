"""
Learning upload-intents should use central config for limits and key helpers.

TDD: This test asserts that the max size in the response honors the central
config, and that the generated storage key follows the helper's shape.
"""
from __future__ import annotations

import os
import re
import uuid
import httpx
import pytest
from httpx import ASGITransport

import importlib


pytestmark = pytest.mark.anyio("asyncio")


async def _client():
    import main  # noqa
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _seed_course_with_task():
    import main  # noqa
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()  # in-memory
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
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name}, headers={"Origin": "http://test"})  # type: ignore
    return student.session_id, course_id, task_id


class _Recorder:
    def __init__(self):
        self.calls: list[dict] = []

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]) -> dict:
        self.calls.append({"bucket": bucket, "key": key, "expires_in": expires_in, "headers": headers})
        return {"url": f"http://storage/{bucket}/{key}", "headers": headers}

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": None}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"http://storage/{bucket}/{key}", "expires_at": "2099-01-01T00:00:00Z"}


async def test_learning_upload_intent_uses_config_limit_and_key_shape(monkeypatch):
    # Force distinct config to detect if route reads central config
    monkeypatch.setenv("LEARNING_MAX_UPLOAD_BYTES", "3145728")  # 3 MiB
    # Ensure bucket from config to simplify assertion
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "subs-cfg")

    # Reload config and route modules to pick up env
    if "backend.storage.config" in importlib.sys.modules:
        importlib.reload(importlib.import_module("backend.storage.config"))
    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import routes.learning as learning  # noqa
    import main  # noqa

    # Override adapter to record bucket/key
    recorder = _Recorder()
    learning.set_storage_adapter(recorder)  # type: ignore[arg-type]

    sid, course_id, task_id = await _seed_course_with_task()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.PNG", "mime_type": "image/png", "size_bytes": 1024},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 200
    body = r.json()
    assert int(body.get("max_size_bytes", 0)) == 3 * 1024 * 1024
    assert recorder.calls, "adapter should be called"
    call = recorder.calls[-1]
    assert call["bucket"] == "subs-cfg"
    # Key shape: submissions/{course}/{task}/{student}/{ts-uuid}.ext
    assert call["key"].startswith("submissions/")
    assert call["key"].endswith(".png")
    assert re.match(r"^submissions/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9]{13}-[0-9a-f]+\.png$", call["key"]) is not None
