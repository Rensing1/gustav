"""
Learning API — Production strict CSRF for submissions.

In production (GUSTAV_ENV=prod), POST /submissions must require Origin or
Referer and reject requests without either header, regardless of the
STRICT_CSRF_SUBMISSIONS toggle.
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
async def test_prod_requires_origin_or_referer(monkeypatch: pytest.MonkeyPatch):
    # Force prod environment; ensure STRICT_CSRF_SUBMISSIONS is irrelevant here
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.delenv("STRICT_CSRF_SUBMISSIONS", raising=False)
    session_store = install_session_store(monkeypatch, main)
    # Pin environment override as additional guard against import-order drift
    try:
        main.RUNTIME.settings.override_environment("prod")
    except Exception:
        pass
    student = session_store.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        res = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            json={"kind": "text", "text_body": "hi"},
        )
    assert res.status_code == 403
    # If this ever fails, include diagnostic headers in the assertion message
    assert res.json().get("detail") == "csrf_violation", (
        f"detail={res.json().get('detail')}, "
        f"csrf={res.headers.get('X-CSRF-Diag')}, submissions={res.headers.get('X-Submissions-Diag')}"
    )
