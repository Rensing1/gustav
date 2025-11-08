"""
Learning API — Lazy storage wiring for upload-intents

Why:
    When Supabase is not reachable during app startup, the storage adapter
    remains Null and upload-intents return 503. We add a lazy wiring attempt
    on first request. This test simulates a failing startup wiring and verifies
    that the first upload-intent triggers a successful re-wire and returns 200.
"""
from __future__ import annotations

import os
import sys
import types
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
BACKEND_DIR = REPO_ROOT / "backend"
for path in (WEB_DIR, BACKEND_DIR, REPO_ROOT):
    if str(path) not in os.sys.path:
        os.sys.path.insert(0, str(path))


def _install_flaky_supabase_module() -> None:
    """Install a fake `supabase` module that fails once, then succeeds.

    - First call to `create_client(url, key)` raises SupabaseException.
    - Second and subsequent calls return a client with Storage methods used by
      the adapter (create_signed_upload_url/create_signed_url/stat/remove).
    """

    class SupabaseException(Exception):
        pass

    class _FakeBucket:
        def create_signed_upload_url(self, key: str):
            return {"url": f"https://fake.storage.local/{key}?signature=xyz"}

        def create_signed_url(self, key: str, expires_in: int, options=None):
            return {"url": f"https://fake.storage.local/{key}?download=1"}

        def stat(self, key: str):
            return {"size": 0, "mimetype": "application/octet-stream"}

        def remove(self, paths: list[str]):
            return None

    class _FakeStorage:
        def from_(self, bucket: str):
            return _FakeBucket()

    class _FakeClient:
        def __init__(self) -> None:
            self.storage = _FakeStorage()

    state = {"calls": 0}

    def create_client(url: str, key: str):  # noqa: D401 - simple factory
        state["calls"] += 1
        if state["calls"] == 1:
            raise SupabaseException("startup connection refused")
        return _FakeClient()

    mod = types.SimpleNamespace(create_client=create_client, SupabaseException=SupabaseException)
    sys.modules["supabase"] = mod  # type: ignore[assignment]


async def _client(app):
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _prepare_fixture(main):
    # Fresh in-memory session store
    from identity_access.stores import SessionStore

    main.SESSION_STORE = SessionStore()  # type: ignore
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore

    async with (await _client(main.app)) as c:
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
            json={"instruction_md": "Aufgabe", "criteria": ["K"], "max_attempts": 3},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        module_id = r_module.json()["id"]
        r_vis = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name})  # type: ignore
    return student.session_id, course_id, task_id


@pytest.mark.anyio
async def test_upload_intent_lazy_rewire_on_first_request(monkeypatch):
    # Ensure clean import state for startup wiring
    for name in list(sys.modules.keys()):
        if name in {"main", "routes.learning", "backend.web.routes.learning"}:
            del sys.modules[name]

    # Set env to enable wiring and disable proxy/stub for a stable assertion
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")

    # Install fake supabase module: first call fails (startup), subsequent succeed.
    _install_flaky_supabase_module()

    # Import app (startup wiring runs and fails once)
    import main  # type: ignore  # noqa: F401
    import routes.learning as learning  # type: ignore
    from teaching.storage import NullStorageAdapter  # type: ignore

    # Assert still Null after startup wiring failure
    assert isinstance(learning.STORAGE_ADAPTER, NullStorageAdapter)

    # Prepare course/task data
    student_sid, course_id, task_id = await _prepare_fixture(main)  # type: ignore

    # First upload-intent should trigger lazy wiring and succeed
    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "storage_key" in data and isinstance(data["storage_key"], str)
        assert "url" in data and isinstance(data["url"], str)


@pytest.mark.anyio
async def test_upload_intent_uses_same_origin_proxy_when_enabled(monkeypatch):
    """When proxy is enabled and presign host matches SUPABASE_URL, return proxied URL.

    Setup:
        - Set SUPABASE_URL to a host we control (supabase.local:54321).
        - Enable ENABLE_STORAGE_UPLOAD_PROXY and disable dev upload stub.
        - Inject a minimal fake storage adapter whose presign_upload returns
          a URL on the same host as SUPABASE_URL.

    Expectation:
        - The upload-intent responds 200 and returns a URL that starts with
          the internal proxy endpoint (/api/learning/internal/upload-proxy?url=...).
        - Response contains normalized headers including content-type.
    """
    # Ensure clean import state for a predictable app
    for name in list(sys.modules.keys()):
        if name in {"main", "routes.learning", "backend.web.routes.learning"}:
            del sys.modules[name]

    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")

    import main  # type: ignore  # noqa: F401
    import routes.learning as learning  # type: ignore

    class _FakeAdapter:
        def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]):
            # Return a presigned URL with the same host as SUPABASE_URL so proxying applies
            return {
                "url": f"http://supabase.local:54321/storage/v1/object/sign/{bucket}/{key}?signature=abc",
                "headers": headers,
                "method": "PUT",
            }

    # Inject fake adapter and bucket so the route can proceed to presign
    learning.set_storage_adapter(_FakeAdapter())  # type: ignore[attr-defined]

    # Prepare teacher/student/course/task via helpers
    student_sid, course_id, task_id = await _prepare_fixture(main)  # type: ignore

    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "bild.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("url"), str)
        assert data["url"].startswith("/api/learning/internal/upload-proxy?url="), data["url"]
        # Headers are normalized to include both lower and canonical casing
        assert data["headers"].get("content-type") == "image/png"
