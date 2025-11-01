"""
Learning API — Strict CSRF policy for submissions (env‑gated)

When STRICT_CSRF_SUBMISSIONS=true, POST /submissions must require Origin or
Referer and reject requests without either header.
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_strict_csrf_requires_origin_or_referer(monkeypatch: pytest.MonkeyPatch):
    # Enable strict mode and create an in-memory session
    monkeypatch.setenv("STRICT_CSRF_SUBMISSIONS", "true")
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        res = await client.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            json={"kind": "text", "text_body": "hi"},
        )
    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"

