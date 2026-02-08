"""
SSR UI — module create must propagate API validation errors.

Why:
    `POST /units/{unit_id}/modules` must not silently fall back to /sections
    when the modular API rejects an invalid phase_id.
"""

from __future__ import annotations

import types
import uuid

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeInternalApiClient:
    def __init__(self, routes: dict[tuple[str, str], _FakeResponse], calls: list[tuple[str, str, dict | None]]):
        self._routes = routes
        self._calls = calls
        self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict | None = None):
        self._calls.append(("POST", url, json))
        return self._routes.get(("POST", url), _FakeResponse(404, {"error": "not_found"}))


@pytest.mark.anyio
async def test_unit_modules_create_invalid_phase_id_returns_400_without_sections_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ssr-modules-create-err", name="Teacher", roles=["teacher"])  # type: ignore
    unit_id = str(uuid.uuid4())
    invalid_phase_id = str(uuid.uuid4())
    csrf_token = main._get_or_create_csrf_token(teacher.session_id)  # type: ignore[attr-defined]

    calls: list[tuple[str, str, dict | None]] = []
    routes = {
        ("POST", f"/api/teaching/units/{unit_id}/modules"): _FakeResponse(
            400, {"error": "bad_request", "detail": "invalid_phase_id"}
        ),
        ("POST", f"/api/teaching/units/{unit_id}/sections"): _FakeResponse(201, {"id": str(uuid.uuid4())}),
    }
    monkeypatch.setattr(
        main,
        "_internal_api_client",
        lambda: _FakeInternalApiClient(routes, calls),
        raising=True,
    )

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.post(
            f"/units/{unit_id}/modules",
            data={"title": "Neues Modul", "phase_id": invalid_phase_id, "csrf_token": csrf_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert resp.status_code == 400
    assert "invalid_phase_id" in resp.text
    assert ("POST", f"/api/teaching/units/{unit_id}/sections", {"title": "Neues Modul"}) not in calls


@pytest.mark.anyio
async def test_unit_modules_create_missing_phase_id_returns_400_without_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ssr-modules-create-missing-phase", name="Teacher", roles=["teacher"])  # type: ignore
    unit_id = str(uuid.uuid4())
    csrf_token = main._get_or_create_csrf_token(teacher.session_id)  # type: ignore[attr-defined]

    calls: list[tuple[str, str, dict | None]] = []
    routes = {
        ("POST", f"/api/teaching/units/{unit_id}/modules"): _FakeResponse(201, {"id": str(uuid.uuid4())}),
        ("POST", f"/api/teaching/units/{unit_id}/sections"): _FakeResponse(201, {"id": str(uuid.uuid4())}),
    }
    monkeypatch.setattr(
        main,
        "_internal_api_client",
        lambda: _FakeInternalApiClient(routes, calls),
        raising=True,
    )

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.post(
            f"/units/{unit_id}/modules",
            data={"title": "Neues Modul", "csrf_token": csrf_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert resp.status_code == 400
    assert "invalid_phase_id" in resp.text
    assert calls == []
