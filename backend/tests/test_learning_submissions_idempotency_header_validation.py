"""
Learning API — Idempotency-Key header validation.

Ensures the API rejects invalid tokens (non-ASCII, spaces, symbols) per regex
^[A-Za-z0-9_-]{1,64}$ and accepts a valid one.
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport

import os
from pathlib import Path


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


@pytest.mark.anyio
async def test_submission_rejects_invalid_idempotency_key_regex():
    """Header with spaces/symbols must yield 400 invalid_input."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
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
async def test_submission_allows_valid_idempotency_key_pattern():
    """Valid token characters should pass header validation layer (task may 404)."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
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
