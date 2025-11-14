"""
Learning API — Storage upload proxy fallback (same-origin)

Why:
    Some deployments cannot set Storage CORS. As a fallback, when
    ENABLE_STORAGE_UPLOAD_PROXY=true, the upload-intent should return a
    same-origin proxy URL. The proxy reads the body and forwards it to the
    presigned URL server-side, then returns sha256 + size_bytes.
"""
from __future__ import annotations

import os
import uuid
from uuid import UUID

import httpx
import pytest
from httpx import ASGITransport
from fastapi.routing import APIRoute


pytestmark = pytest.mark.anyio("asyncio")

import main  # type: ignore  # noqa: E402
import routes.learning as learning  # type: ignore  # noqa: E402


class _FakeAdapter:
    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]):
        # Minimal presigned URL to a supabase-like host
        presign_headers = {
            "x-upsert": "true",
            "Content-Type": headers.get("Content-Type", "application/octet-stream"),
        }
        return {
            "url": f"http://127.0.0.1:54321/storage/v1/object/sign/{bucket}/{key}?token=abc",
            "headers": presign_headers,
            "method": "PUT",
        }

    def delete_object(self, *, bucket: str, key: str):
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str):
        return {"url": f"http://127.0.0.1:54321/storage/v1/object/sign/{bucket}/{key}?download=1"}


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_upload_proxy_flow(monkeypatch):
    # Enable proxy and ensure adapter configured
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    learning.set_storage_adapter(_FakeAdapter())

    # Seed minimal course/task via teaching API
    from identity_access.stores import SessionStore  # type: ignore

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
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        await c.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"sub": student.sub, "name": student.name},  # type: ignore
            headers={"Origin": "http://test"},
        )

    # Monkeypatch requests.put used by proxy to avoid network
    body_sent = {}

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        body_sent["url"] = kwargs.get("url")
        body_sent["data"] = kwargs.get("payload")
        proxy_headers = dict(kwargs.get("headers") or {})
        if not proxy_headers and kwargs.get("content_type"):
            proxy_headers = {"Content-Type": kwargs.get("content_type")}
        body_sent["headers"] = proxy_headers
        return _Resp()

    import routes.learning as lr  # type: ignore
    try:  # type: ignore[attr-defined]
        import backend.web.routes.learning as lr_backend  # type: ignore
    except ImportError:  # pragma: no cover
        lr_backend = None  # type: ignore
    monkeypatch.setattr(lr, "_async_forward_upload", fake_forward)
    if lr_backend is not None:
        monkeypatch.setattr(lr_backend, "_async_forward_upload", fake_forward)
    # Some suites reload routes.learning. Patch the actual FastAPI endpoint globals as well.
    for route in main.app.routes:
        if isinstance(route, APIRoute) and route.path == "/api/learning/internal/upload-proxy":
            route.endpoint.__globals__["_async_forward_upload"] = fake_forward
            break
    else:  # pragma: no cover - defensive to surface wiring issues
        raise AssertionError("upload-proxy route not registered on FastAPI app")

    # Request upload-intent; expect same-origin proxy url
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_intent = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "x.png", "mime_type": "image/png", "size_bytes": 128},
            headers={"Origin": "http://test"},
        )
        assert r_intent.status_code == 200
        intent = r_intent.json()
        assert intent["url"].startswith("/api/learning/internal/upload-proxy")
        # PUT to proxy
        data = b"hello"
        r_put = await c.put(intent["url"], headers={"Origin": "http://test", "Content-Type": "image/png"}, content=data)
        assert r_put.status_code == 200
        j = r_put.json()
        assert int(j.get("size_bytes", 0)) == len(data)
        # Upstream captured and content-type preserved
        assert body_sent.get("headers", {}).get("Content-Type") == "image/png"
        assert body_sent.get("headers", {}).get("x-upsert") == "true"
