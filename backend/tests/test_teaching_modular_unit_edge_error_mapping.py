"""
Teaching API — modular editor hardening without DB dependency.

Why:
    - Unknown module ids in edge creation must return 404 (OpenAPI contract).
    - In-memory fallback repo must not crash modular endpoints with 500.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.teaching as teaching  # type: ignore
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


def _teacher_session(monkeypatch: pytest.MonkeyPatch, sub: str):
    store = install_session_store(monkeypatch, main)
    return store.create(sub=sub, name="Teacher", roles=["teacher"])


@pytest.mark.anyio
async def test_create_edge_unknown_module_returns_404_instead_of_constraint_400(
    monkeypatch: pytest.MonkeyPatch,
):
    teacher = _teacher_session(monkeypatch, "t-edge-map-404")
    unit_id = str(uuid.uuid4())
    from_id = str(uuid.uuid4())
    to_unknown_id = str(uuid.uuid4())

    class _CheckViolation(Exception):
        sqlstate = "23514"

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def list_unit_modules_for_author(self, *, unit_id: str, author_id: str):
            assert unit_id
            assert author_id
            return [{"id": from_id}]

        def create_unit_module_edge_for_author(self, **_kwargs):
            raise _CheckViolation("module_not_in_unit")

    repo = _StubRepo()
    monkeypatch.setattr(teaching, "_get_repo", lambda: repo, raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": from_id, "to_module_id": to_unknown_id},
        )

    assert resp.status_code == 404, resp.text
    assert resp.json().get("error") == "not_found"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_modular_phases_with_in_memory_repo_returns_503_not_500(monkeypatch: pytest.MonkeyPatch):
    teacher = _teacher_session(monkeypatch, "t-mod-fallback-503")

    class _NoModularRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

    teaching.set_repo(_NoModularRepo())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.get("/api/teaching/units/00000000-0000-0000-0000-000000000001/phases")

    assert resp.status_code == 503
    assert resp.json().get("error") == "service_unavailable"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_modular_unit_with_in_memory_repo_returns_503_service_unavailable(monkeypatch: pytest.MonkeyPatch):
    teacher = _teacher_session(monkeypatch, "t-mod-fallback-create-503")
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})

    assert resp.status_code == 503, resp.text
    assert resp.json().get("error") == "service_unavailable"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_legacy_edge_delete_sets_deprecation_headers_with_concrete_successor_link(
    monkeypatch: pytest.MonkeyPatch,
):
    teacher = _teacher_session(monkeypatch, "t-legacy-edge-header")
    unit_id = str(uuid.uuid4())
    from_id = str(uuid.uuid4())
    to_id = str(uuid.uuid4())

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def delete_unit_module_edge_for_author(self, **_kwargs):
            return True

    monkeypatch.setattr(teaching, "_get_repo", lambda: _StubRepo(), raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.request(
            "DELETE",
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": from_id, "to_module_id": to_id},
        )

    assert resp.status_code == 204, resp.text
    assert resp.headers.get("Deprecation") == "true"
    assert resp.headers.get("Sunset") == "Tue, 30 Jun 2026 23:59:59 GMT"
    assert resp.headers.get("Link") == (
        f'</api/teaching/units/{unit_id}/modules/{from_id}/edges/{to_id}>; rel="successor-version"'
    )


@pytest.mark.anyio
async def test_legacy_edge_delete_error_does_not_emit_deprecation_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    """Deprecation/Sunset/Link headers are only valid for successful legacy deletes."""
    teacher = _teacher_session(monkeypatch, "t-legacy-edge-header-error")
    unit_id = str(uuid.uuid4())
    from_id = str(uuid.uuid4())
    to_id = str(uuid.uuid4())

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def delete_unit_module_edge_for_author(self, **_kwargs):
            return False

    monkeypatch.setattr(teaching, "_get_repo", lambda: _StubRepo(), raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.request(
            "DELETE",
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": from_id, "to_module_id": to_id},
        )

    assert resp.status_code == 404, resp.text
    assert resp.headers.get("Deprecation") is None
    assert resp.headers.get("Sunset") is None
    assert resp.headers.get("Link") is None


@pytest.mark.anyio
async def test_create_edge_does_not_mask_unexpected_typeerror_from_repo(
    monkeypatch: pytest.MonkeyPatch,
):
    """Unexpected TypeError inside repo code must not be treated as signature fallback."""

    teacher = _teacher_session(monkeypatch, "t-edge-typeerror")
    unit_id = str(uuid.uuid4())
    from_id = str(uuid.uuid4())
    to_id = str(uuid.uuid4())

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def list_unit_modules_for_author(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if kwargs:
                # Simulate an implementation bug while still accepting kwargs.
                raise TypeError("internal_boom")
            return [{"id": from_id}, {"id": to_id}]

        def create_unit_module_edge_for_author(self, **_kwargs):
            return {"from": from_id, "to": to_id}

    monkeypatch.setattr(teaching, "_get_repo", lambda: _StubRepo(), raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": from_id, "to_module_id": to_id},
        )

    assert resp.status_code == 500, resp.text


@pytest.mark.anyio
async def test_create_edge_maps_invalid_unit_type_from_precheck_to_contract_400(
    monkeypatch: pytest.MonkeyPatch,
):
    teacher = _teacher_session(monkeypatch, "t-edge-precheck-400")
    unit_id = str(uuid.uuid4())
    from_id = str(uuid.uuid4())
    to_id = str(uuid.uuid4())

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

        def list_unit_modules_for_author(self, **_kwargs):
            raise ValueError("invalid_unit_type")

        def create_unit_module_edge_for_author(self, **_kwargs):  # pragma: no cover - must not run
            raise AssertionError("create must not be called when precheck fails")

    monkeypatch.setattr(teaching, "_get_repo", lambda: _StubRepo(), raising=True)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": from_id, "to_module_id": to_id},
        )

    assert resp.status_code == 400, resp.text
    assert resp.json().get("detail") == "invalid_unit_type"
