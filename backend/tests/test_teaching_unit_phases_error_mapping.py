"""
Teaching API — unit phases error mapping.

Why:
    Unexpected runtime errors must not be masked as authorization failures.
    Otherwise diagnostics and API semantics drift (403 vs real server fault).
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.teaching as teaching  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_list_unit_phases_unexpected_repo_error_returns_500(monkeypatch: pytest.MonkeyPatch):
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-phases-boom", name="Teach", roles=["teacher"])  # type: ignore

    class _BoomRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def list_unit_phases_for_author(self, _unit_id: str, _author_sub: str):
            raise RuntimeError("db_down")

    repo = _BoomRepo()
    monkeypatch.setattr(teaching, "_get_repo", lambda: repo, raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.get("/api/teaching/units/00000000-0000-0000-0000-000000000001/phases")

    assert resp.status_code == 500
