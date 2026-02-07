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
from starlette.requests import Request
from utils.db import require_db_or_skip as _require_db_or_skip

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
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for unit phases SSR UI test")

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
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for unit phases SSR UI cache test")

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


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("err", "expected_status"),
    [
        ("forbidden", 403),
        ("not_found", 404),
        ("backend_error", 503),
    ],
)
async def test_unit_phases_page_maps_phase_fetch_errors_to_http_status(
    monkeypatch: pytest.MonkeyPatch, err: str, expected_status: int
):
    unit_id = "11111111-1111-1111-1111-111111111111"

    class _DummyResponse:
        status_code = 200

        def json(self) -> dict:
            return {"id": unit_id, "title": "Unit", "unit_type": "modular"}

    class _DummyClient:
        def __init__(self) -> None:
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def get(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return _DummyResponse()

    class _DummyClientCtx:
        async def __aenter__(self):
            return _DummyClient()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    async def _fake_fetch(_unit_id: str, *, session_id: str) -> tuple[list[dict], str | None]:
        assert _unit_id == unit_id
        assert session_id == "sid-phases-status"
        return [], err

    monkeypatch.setattr(main, "_internal_api_client", lambda: _DummyClientCtx(), raising=True)
    monkeypatch.setattr(main, "_fetch_unit_phases_for_unit", _fake_fetch, raising=True)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/units/{unit_id}/phases",
        "headers": [(b"cookie", b"gustav_session=sid-phases-status")],
        "query_string": b"",
        "state": {},
        "client": ("test", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    request.state.user = {"sub": "t-ui-phases-status", "role": "teacher", "roles": ["teacher"]}

    resp = await main.unit_phases_index(request, unit_id)
    assert resp.status_code == expected_status
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_unit_phases_page_accepts_teacher_in_roles_fallback(monkeypatch: pytest.MonkeyPatch):
    """Teacher SSR phases page must honor roles-list fallback via _user_has_role."""
    unit_id = "22222222-2222-2222-2222-222222222222"

    class _DummyResponse:
        status_code = 200

        def json(self) -> dict:
            return {"id": unit_id, "title": "Unit", "unit_type": "modular"}

    class _DummyClient:
        def __init__(self) -> None:
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def get(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return _DummyResponse()

    class _DummyClientCtx:
        async def __aenter__(self):
            return _DummyClient()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    async def _fake_fetch(_unit_id: str, *, session_id: str) -> tuple[list[dict], str | None]:
        assert _unit_id == unit_id
        assert session_id == "sid-phases-roles"
        return [], None

    monkeypatch.setattr(main, "_internal_api_client", lambda: _DummyClientCtx(), raising=True)
    monkeypatch.setattr(main, "_fetch_unit_phases_for_unit", _fake_fetch, raising=True)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/units/{unit_id}/phases",
        "headers": [(b"cookie", b"gustav_session=sid-phases-roles")],
        "query_string": b"",
        "state": {},
        "client": ("test", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    request.state.user = {"sub": "t-ui-phases-roles", "role": "student", "roles": ["teacher"]}

    resp = await main.unit_phases_index(request, unit_id)
    assert resp.status_code == 200
    assert "Phasen" in resp.body.decode("utf-8")


@pytest.mark.anyio
async def test_modular_editor_phase_new_fragment_accepts_teacher_in_roles_fallback():
    """New modular editor routes should not depend on primary role only."""
    unit_id = "33333333-3333-3333-3333-333333333333"
    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/units/{unit_id}/modular-editor/phase/new",
        "headers": [(b"cookie", b"gustav_session=sid-mod-editor-fallback")],
        "query_string": b"",
        "state": {},
        "client": ("test", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    request.state.user = {"sub": "t-mod-editor-fallback", "role": "student", "roles": ["teacher"]}

    resp = await main.modular_editor_phase_new_fragment(request, unit_id)
    assert resp.status_code == 200
    assert "Neue Phase" in resp.body.decode("utf-8")
