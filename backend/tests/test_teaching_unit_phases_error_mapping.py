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
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


def _teacher_session(monkeypatch: pytest.MonkeyPatch, sub: str):
    store = install_session_store(monkeypatch, main)
    return store.create(sub=sub, name="Teach", roles=["teacher"])


@pytest.mark.anyio
async def test_list_unit_phases_unexpected_repo_error_returns_500(monkeypatch: pytest.MonkeyPatch):
    teacher = _teacher_session(monkeypatch, "t-phases-boom")

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


@pytest.mark.anyio
async def test_update_unit_phase_maps_permission_error_to_403(monkeypatch: pytest.MonkeyPatch):
    """PATCH phase rename must not leak repo PermissionError as 500."""

    teacher = _teacher_session(monkeypatch, "t-phases-perm")

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def update_unit_phase_title(self, _unit_id: str, _phase_id: str, _title: str, _author_sub: str):
            raise PermissionError("forbidden")

    monkeypatch.setattr(teaching, "_get_repo", lambda: _StubRepo(), raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.patch(
            "/api/teaching/units/00000000-0000-0000-0000-000000000001/phases/00000000-0000-0000-0000-000000000002",
            json={"title": "Neu"},
        )

    assert resp.status_code == 403, resp.text
    assert resp.json().get("error") == "forbidden"
    assert resp.headers.get("Cache-Control") == "private, no-store"
