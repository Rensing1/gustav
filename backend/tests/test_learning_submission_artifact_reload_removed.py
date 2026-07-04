from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

import main  # type: ignore
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_submission_artifact_reload_endpoint_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retired artifact reload routes stay explicitly gone for legacy callers."""
    store = install_session_store(monkeypatch, main)
    student = store.create(sub="s-artifact-reload-removed", name="S", roles=["student"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        resp = await client.get("/learning/courses/c1/tasks/t1/submissions/s1/artifact")

    assert resp.status_code == 410
