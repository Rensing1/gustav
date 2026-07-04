"""
Learning API — Default strict CSRF for submissions (dev = prod).

Goal: Without any env toggles, POST /submissions requires Origin or Referer
and rejects requests without either header.
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport

import main  # type: ignore  # noqa: E402
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_default_requires_origin_or_referer(monkeypatch: pytest.MonkeyPatch):
    # Default env (no STRICT_CSRF_SUBMISSIONS, no GUSTAV_ENV=prod override)
    monkeypatch.delenv("STRICT_CSRF_SUBMISSIONS", raising=False)
    try:
        main.RUNTIME.settings.override_environment(None)
    except Exception:
        pass
    session_store = install_session_store(monkeypatch, main)
    student = session_store.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        res = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            json={"kind": "text", "text_body": "hi"},
        )
    assert res.status_code == 403
    assert res.json().get("detail") == "csrf_violation"
