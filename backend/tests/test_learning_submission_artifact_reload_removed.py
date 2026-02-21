from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_submission_artifact_reload_endpoint_is_removed() -> None:
    """The UI must not expose a dedicated artifact reload endpoint."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-artifact-reload-removed", name="S", roles=["student"])  # type: ignore

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        resp = await client.get("/learning/courses/c1/tasks/t1/submissions/s1/artifact")

    assert resp.status_code == 404

