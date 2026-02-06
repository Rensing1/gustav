"""
SSR UI: teacher phase editor page for modular learning units.

Why:
    The API for modular unit phases exists, but the teacher SSR UI must expose
    it; otherwise teachers can create "modular" units yet have no way to manage
    phases (the core organizer concept).
"""

from __future__ import annotations

import types
from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_unit_phases_page_renders_for_modular_unit():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-phases-1", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Phases UI", "unit_type": "modular"})
        assert r_unit.status_code == 201
        uid = r_unit.json()["id"]

        page = await c.get(f"/units/{uid}/phases")
        assert page.status_code == 200
        html = page.text
        assert "Phasen" in html
        # Default phase exists for modular units.
        assert "Phase 1" in html


@pytest.mark.anyio
async def test_unit_phases_create_hx_response_sets_private_no_store_header():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-phases-cache-create", name="Teacher", roles=["teacher"])
    csrf = main._get_or_create_csrf_token(teacher.session_id)  # type: ignore[attr-defined]

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Cache UI", "unit_type": "modular"})
        assert r_unit.status_code == 201
        uid = r_unit.json()["id"]

        r = await c.post(
            f"/units/{uid}/phases",
            data={"csrf_token": csrf, "title": "Neue Phase"},
            headers={"HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_unit_phases_reorder_error_sets_private_no_store_header(monkeypatch: pytest.MonkeyPatch):
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-phases-cache-reorder", name="Teacher", roles=["teacher"])
    csrf = main._get_or_create_csrf_token(teacher.session_id)  # type: ignore[attr-defined]

    class _FakeInternalApiClient:
        def __init__(self):
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    monkeypatch.setattr(main, "_internal_api_client", lambda: _FakeInternalApiClient(), raising=True)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.post(
            "/units/11111111-1111-1111-1111-111111111111/phases/reorder",
            data={"csrf_token": csrf, "id": "phase_11111111-1111-1111-1111-111111111111"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert r.status_code == 400
    assert r.json().get("detail") == "reorder_failed"
    assert r.headers.get("Cache-Control") == "private, no-store"
