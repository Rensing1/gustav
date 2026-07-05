"""
Learning API — Idempotency-Key header validation.

Ensures the API rejects invalid tokens (non-ASCII, spaces, symbols) per regex
^[A-Za-z0-9_-]{1,64}$ and accepts a valid one.
"""
from __future__ import annotations

import importlib
import uuid
import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

main = importlib.import_module("backend.web.main")
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_submission_rejects_invalid_idempotency_key_regex(monkeypatch: pytest.MonkeyPatch):
    """Header with spaces/symbols must yield 400 invalid_input."""
    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        # Missing Origin/Referer triggers CSRF block; include Origin to reach validation
        r = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            headers={"Idempotency-Key": "bad token!", "Origin": "http://test"},
            json={"kind": "text", "text_body": "hi"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_input"


@pytest.mark.anyio
async def test_submission_allows_valid_idempotency_key_pattern(monkeypatch: pytest.MonkeyPatch):
    """Valid token characters should pass header validation layer (task may 404)."""
    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            headers={"Idempotency-Key": "abc_DEF-123", "Origin": "http://test"},
            json={"kind": "text", "text_body": "hi"},
        )
    # After header validation, request proceeds to auth/lookup and may yield
    # 400 invalid_uuid, 403 forbidden (not member), or 404 not_found. It must
    # not fail with 400 invalid_input (header regex).
    if r.status_code == 400:
        assert r.json().get("detail") != "invalid_input"
