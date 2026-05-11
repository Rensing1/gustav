"""
Tests for authentication-enforcing middleware.

Requirements:
- HTML requests without session → 302 to /auth/login with return-to
- JSON/API requests without session → 401 JSON
- HTMX requests without session → 401 + HX-Redirect header (with return-to)
- Allowlist: /auth/*, /health, /static/* are not redirected
"""

import pytest
import httpx
from httpx import ASGITransport
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.cli_tokens import InMemoryCLITokenStore  # type: ignore
from routes import teaching as teaching_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _install_cli_token(
    monkeypatch: pytest.MonkeyPatch,
    *,
    scopes: list[str],
    roles: list[str],
    user_sub: str = "teacher-cli-auth",
):
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    created = store.create_token(
        user_sub=user_sub,
        label="Laptop",
        scopes=scopes,
        ttl_seconds=3_600,
    )
    monkeypatch.setattr(main, "CLI_TOKEN_STORE", store)
    monkeypatch.setattr(main, "_roles_for_cli_sub", lambda sub: list(roles))
    return store, created


@pytest.mark.anyio
async def test_html_request_without_session_redirects_to_login():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/", headers={"Accept": "text/html"}, follow_redirects=False)
    assert r.status_code in (301, 302, 303)
    loc = r.headers.get("location", "")
    p = urlparse(loc)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/"]


@pytest.mark.anyio
async def test_json_request_without_session_returns_401():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/api/me", headers={"Accept": "application/json"})
    assert r.status_code == 401
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_htmx_request_without_session_returns_401_with_hx_redirect():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/dashboard", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 401
    hx = r.headers.get("HX-Redirect", "")
    p = urlparse(hx)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/dashboard"]


@pytest.mark.anyio
async def test_htmx_unauthenticated_prefers_hx_current_url_for_return_to():
    """HTMX posts (e.g., /submit) should redirect back to the browser page, not the endpoint path."""
    headers = {
        "HX-Request": "true",
        # HTMX sends the full browser URL; the middleware must only use the path part.
        "HX-Current-URL": "https://app.localhost/learning/courses/c1/units/u1",
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.post("/learning/courses/c1/tasks/t1/submit", headers=headers, follow_redirects=False)
    assert r.status_code == 401
    hx = r.headers.get("HX-Redirect", "")
    p = urlparse(hx)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/learning/courses/c1/units/u1"]


@pytest.mark.anyio
async def test_html_post_unauthenticated_prefers_referer_for_return_to():
    """Non-HTMX POSTs must not return-to a POST-only endpoint (would cause 405 after login)."""
    headers = {
        "Accept": "text/html",
        "Referer": "https://app.localhost/learning/courses/c1/units/u1",
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.post("/learning/courses/c1/tasks/t1/submit", headers=headers, follow_redirects=False)
    assert r.status_code in (301, 302, 303)
    loc = r.headers.get("location", "")
    p = urlparse(loc)
    assert p.path == "/auth/login"
    qs = parse_qs(p.query)
    assert qs.get("redirect") == ["/learning/courses/c1/units/u1"]


@pytest.mark.anyio
async def test_allowlist_paths_not_redirected():
    # StaticFiles responses can be streaming; avoid exercising them via ASGITransport
    # here and instead assert the middleware's allowlist predicate directly.
    assert main._is_public_path("/static/css/gustav.css")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_auth = await client.get("/auth/login", follow_redirects=False)
        r_health = await client.get("/health")

    assert r_auth.status_code in (200, 302, 303)
    assert r_health.status_code == 200


@pytest.mark.anyio
async def test_favicon_is_allowlisted():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_favicon = await client.get("/favicon.ico", follow_redirects=False)
    # It may 404, but must not redirect to login
    assert r_favicon.status_code != 302 or r_favicon.headers.get("location") != "/auth/login"


@pytest.mark.anyio
async def test_cli_bearer_can_authenticate_teaching_units_without_jwt_verification(monkeypatch):
    _, created = _install_cli_token(monkeypatch, scopes=["read"], roles=["teacher"])

    def _fail_jwt_verification(token, cfg):  # pragma: no cover - called only on regression
        raise AssertionError("CLI tokens must not be sent to JWT verification")

    monkeypatch.setattr(main, "verify_bearer_token", _fail_jwt_verification)

    class StubRepo:
        def list_units_for_author(self, *, author_id: str, limit: int, offset: int):
            assert author_id == "teacher-cli-auth"
            return []

    monkeypatch.setattr(teaching_routes, "_REPO", StubRepo())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/units",
            headers={"Authorization": f"Bearer {created.raw_token}"},
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_cli_bearer_is_rejected_outside_teaching_authoring_paths(monkeypatch):
    _, created = _install_cli_token(monkeypatch, scopes=["read"], roles=["teacher"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/views/teacher-home",
            headers={"Authorization": f"Bearer {created.raw_token}"},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_cli_bearer_cannot_manage_profile_cli_tokens(monkeypatch):
    store, created = _install_cli_token(
        monkeypatch,
        scopes=["read", "write", "delete"],
        roles=["teacher"],
    )

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post(
            "/api/app/profile/cli-tokens",
            headers={"Authorization": f"Bearer {created.raw_token}"},
            json={"label": "Escalated", "scopes": ["read", "write", "delete"], "ttl_days": 30},
        )

    assert response.status_code == 401
    assert len(store.list_tokens("teacher-cli-auth")) == 1


def test_cli_token_store_db_mode_fails_fast_outside_pytest(monkeypatch):
    class BrokenDBStore:
        def __init__(self) -> None:
            raise RuntimeError("db unavailable")

    monkeypatch.setenv("CLI_TOKENS_BACKEND", "db")
    monkeypatch.setattr(main, "DBCLITokenStore", BrokenDBStore)

    with pytest.raises(RuntimeError, match="db unavailable"):
        main._build_cli_token_store(running_under_pytest=False)


@pytest.mark.anyio
async def test_cli_bearer_write_bypasses_browser_csrf_after_scope_and_role_checks(monkeypatch):
    _, created = _install_cli_token(
        monkeypatch,
        scopes=["write"],
        roles=["teacher"],
        user_sub="teacher-cli-write",
    )

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post(
            "/api/teaching/units",
            headers={"Authorization": f"Bearer {created.raw_token}"},
            json={"title": "CLI Unit"},
        )

    assert response.status_code == 201
    assert response.json()["title"] == "CLI Unit"


@pytest.mark.anyio
async def test_cli_bearer_read_token_cannot_write_teaching_units(monkeypatch):
    _, created = _install_cli_token(monkeypatch, scopes=["read"], roles=["teacher"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post(
            "/api/teaching/units",
            headers={"Authorization": f"Bearer {created.raw_token}"},
            json={"title": "CLI Unit"},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_cli_bearer_write_token_cannot_delete_teaching_units(monkeypatch):
    _, created = _install_cli_token(monkeypatch, scopes=["write"], roles=["teacher"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.delete(
            "/api/teaching/units/00000000-0000-4000-8000-000000000001",
            headers={"Authorization": f"Bearer {created.raw_token}"},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_cli_bearer_revoked_token_is_rejected(monkeypatch):
    store, created = _install_cli_token(monkeypatch, scopes=["read"], roles=["teacher"])
    assert store.revoke_token(user_sub="teacher-cli-auth", token_id=created.record.id)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/units",
            headers={"Authorization": f"Bearer {created.raw_token}"},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_cli_bearer_valid_token_without_teacher_role_is_forbidden(monkeypatch):
    _, created = _install_cli_token(monkeypatch, scopes=["read"], roles=["student"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/units",
            headers={"Authorization": f"Bearer {created.raw_token}"},
        )

    assert response.status_code == 403
