"""
Learning internal upload proxy should enforce central size limit before proxying.

This test sets a very small limit and asserts that requests larger than the
limit are rejected with 400 without reaching the upstream.
"""
from __future__ import annotations

import importlib
import os
import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")


async def _client():
    main = importlib.import_module("backend.web.main")
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_internal_upload_proxy_respects_central_limit(monkeypatch):
    # Configure tiny limit and enable proxy
    monkeypatch.setenv("LEARNING_MAX_UPLOAD_BYTES", "16")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    # Ensure URL host validation passes
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    # Reload config and route to pick env
    if "backend.storage.config" in importlib.sys.modules:
        importlib.reload(importlib.import_module("backend.storage.config"))
    if "backend.web.routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("backend.web.routes.learning"))

    main = importlib.import_module("backend.web.main")
    importlib.import_module("backend.web.routes.learning")
    from backend.tests.runtime_auth_helpers import install_session_store

    # Prepare a student session
    session_store = install_session_store(monkeypatch, main)
    student = session_store.create(sub="s-proxy", name="S", roles=["student"])

    # Body larger than limit
    body = b"x" * 32
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": "https://supabase.local:54321/storage/v1/object/test"},
            content=body,
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "size_exceeded"
