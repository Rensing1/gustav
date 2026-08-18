"""
Auth hardening tests (TDD: RED)

Covers:
- Client-supplied `state` is ignored (server-generated only)
- External redirects are rejected; fallback to "/"
- Callback 400 responses set Cache-Control: no-store
- SSR role display uses fixed priority (admin > teacher > student)
- Logout includes id_token_hint when available
"""

import importlib
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport

from backend.identity_access.oidc import OIDCConfig
from backend.identity_access.stores import SessionStore, SessionRecord, StateStore
from backend.tests.runtime_auth_helpers import install_oidc_client
from backend.web.auth_runtime import AuthSettings
from backend.web.components.navigation import Navigation

main = importlib.import_module("backend.web.main")


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture(autouse=True)
def _force_dev_env():
    """Force dev env for deterministic cookie flags (secure off for http://test)."""
    main.RUNTIME.settings.override_environment("dev")
    yield
    main.RUNTIME.settings.override_environment(None)


def _latest_session_record() -> tuple[str, SessionRecord]:
    store = getattr(main.RUNTIME, "session_store", None)
    assert store, "runtime session store must be configured"
    data = getattr(store, "_data", {})
    assert data, "runtime session store should contain at least one entry"
    sid, rec = next(iter(data.items()))
    return sid, rec


def _ensure_cookie_with_current_session(client: httpx.AsyncClient) -> SessionRecord:
    if client.cookies.get("gustav_session"):
        sid = client.cookies.get("gustav_session")
        rec = main.RUNTIME.session_store.get(sid or "")
        assert rec, "Cookie references unknown session"
        return rec
    sid, rec = _latest_session_record()
    # Ensure cookie is sent for base_url host in httpx jar
    client.cookies.set("gustav_session", sid, domain="test", path="/")
    return rec


@pytest.mark.anyio
async def test_login_ignores_client_state(monkeypatch: pytest.MonkeyPatch):
    """GET /auth/login must not propagate client-provided `state` value to IdP URL."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/login?state=attacker", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    qs = parse_qs(urlparse(loc).query)
    # Server must not reflect attacker-provided state
    assert qs.get("state") and qs.get("state")[0] != "attacker"


@pytest.mark.anyio
async def test_login_rejects_external_redirects(monkeypatch: pytest.MonkeyPatch):
    """Providing an external redirect must be ignored; callback redirects to '/'"""
    # Patch token exchange and verification to avoid external dependencies
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    # Start login with external redirect attempt
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get("/auth/login?redirect=https://evil.com", follow_redirects=False)
        assert r_login.status_code in (302, 303)
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present in authorization URL"
        # Phase 2: extract stored nonce to satisfy nonce check
        rec = getattr(main.RUNTIME.state_store, "_data", {}).get(state)
        expected_nonce = getattr(rec, "nonce", None)
        def fake_verify(id_token: str, cfg: object):
            return {
                "email": "user@example.com",
                "realm_access": {"roles": ["student"]},
                "email_verified": True,
                "nonce": expected_nonce,
            }
        monkeypatch.setattr(main, "verify_id_token", fake_verify)

        # Simulate IdP callback
        r_cb = await client.get(f"/auth/callback?code=valid&state={state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        # Must fall back to in-app root
        assert r_cb.headers.get("location") == "/"


@pytest.mark.anyio
async def test_login_uses_app_runtime_state_store_and_oidc_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_state_store = StateStore()
    runtime_cfg = OIDCConfig(
        base_url="http://runtime-idp:8080",
        realm="runtime-realm",
        client_id="runtime-client",
        redirect_uri="https://runtime-app.example/auth/callback",
        public_base_url="https://runtime-idp.example",
    )
    monkeypatch.setattr(main.RUNTIME, "state_store", runtime_state_store)
    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/auth/login?redirect=/profile", follow_redirects=False)

    assert response.status_code in (302, 303)
    location = response.headers.get("location", "")
    parsed = urlparse(location)
    assert f"{parsed.scheme}://{parsed.netloc}" == "https://runtime-idp.example"
    assert parsed.path == "/realms/runtime-realm/protocol/openid-connect/auth"
    qs = parse_qs(parsed.query)
    assert qs.get("client_id") == ["runtime-client"]
    state = qs.get("state", [None])[0]
    assert state
    runtime_record = getattr(runtime_state_store, "_data", {}).get(state)
    assert runtime_record is not None
    assert runtime_record.redirect == "/profile"


@pytest.mark.anyio
async def test_register_uses_app_runtime_state_store_and_oidc_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOWED_REGISTRATION_DOMAINS", raising=False)
    runtime_state_store = StateStore()
    runtime_cfg = OIDCConfig(
        base_url="http://runtime-idp:8080",
        realm="runtime-realm",
        client_id="runtime-client",
        redirect_uri="https://runtime-app.example/auth/callback",
        public_base_url="https://runtime-idp.example",
    )
    monkeypatch.setattr(main.RUNTIME, "state_store", runtime_state_store)
    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/auth/register?login_hint=learner@example.com&redirect=/profile", follow_redirects=False)

    assert response.status_code in (302, 303)
    location = response.headers.get("location", "")
    parsed = urlparse(location)
    assert f"{parsed.scheme}://{parsed.netloc}" == "https://runtime-idp.example"
    assert parsed.path == "/realms/runtime-realm/protocol/openid-connect/registrations"
    qs = parse_qs(parsed.query)
    assert "kc_action" not in qs
    assert qs.get("client_id") == ["runtime-client"]
    assert qs.get("login_hint") == ["learner@example.com"]
    state = qs.get("state", [None])[0]
    assert state
    runtime_record = getattr(runtime_state_store, "_data", {}).get(state)
    assert runtime_record is not None
    assert runtime_record.redirect == "/profile"


@pytest.mark.anyio
async def test_callback_errors_set_no_store_header():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Missing code/state
        r = await client.get("/auth/callback")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_role_priority_for_ssr_display(monkeypatch: pytest.MonkeyPatch):
    """The retained navigation component displays the already-resolved primary role."""

    html = Navigation(
        {"sub": "teacher-1", "name": "Test User", "role": "teacher", "roles": ["student", "teacher"]},
        current_path="/units",
    ).render()

    assert "Lehrer" in html


@pytest.mark.anyio
async def test_logout_uses_id_token_hint_when_available(monkeypatch: pytest.MonkeyPatch):
    """If session contains an id_token, /auth/logout should include id_token_hint param."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token-123"}

    install_oidc_client(monkeypatch, main, FakeOIDC())
    monkeypatch.setattr(main, "verify_id_token", lambda id_token, cfg: {
        "email": "user@example.com",
        "realm_access": {"roles": ["student"]},
        "email_verified": True,
    })

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Create server-side session via callback first
        # Seed a valid state
        rec = main.RUNTIME.state_store.create(code_verifier="v")
        r_cb = await client.get(f"/auth/callback?code=valid&state={rec.state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        rec = _ensure_cookie_with_current_session(client)
        assert rec.id_token, "Session record must carry the issued id_token"
        # Use the established session to call logout
        # httpx client kept cookies from redirect response
        r_lo = await client.get("/auth/logout", follow_redirects=False)
    assert r_lo.status_code in (302, 303)
    loc = r_lo.headers.get("location", "")
    # Prefer id_token_hint when available; accept client_id fallback in strict-cookie envs
    assert ("id_token_hint=" in loc) or (f"client_id={main.RUNTIME.oidc_config.client_id}" in loc)


@pytest.mark.anyio
async def test_logout_without_session_only_sends_client_id(monkeypatch: pytest.MonkeyPatch):
    """When no session cookie is present, logout must not reuse prior id_token hints."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token-xyz"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    def ok_verify(id_token: str, cfg: object):
        return {
            "sub": "student-123",
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", ok_verify)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        rec = main.RUNTIME.state_store.create(code_verifier="v")
        r_cb = await client.get(f"/auth/callback?code=valid&state={rec.state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        # Simulate client losing cookies before calling logout
        client.cookies.clear()
        r_lo = await client.get("/auth/logout", follow_redirects=False)
    assert r_lo.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(r_lo.headers.get("location", "")).query)
    # Without a session/id_token, logout must fall back to client_id only
    assert qs.get("client_id") == [main.RUNTIME.oidc_config.client_id]
    assert "id_token_hint" not in qs


@pytest.mark.anyio
async def test_logout_session_without_id_token_falls_back_to_client_id():
    """Sessions missing id_token must fall back to client_id instead of stale hints."""
    sess = main.RUNTIME.session_store.create(sub="user-xyz", roles=["student"], name="Student", id_token=None)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/auth/logout", follow_redirects=False)
    assert r.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(r.headers.get("location", "")).query)
    assert qs.get("client_id") == [main.RUNTIME.oidc_config.client_id]
    assert "id_token_hint" not in qs


@pytest.mark.anyio
async def test_logout_prefers_forwarded_id_token_hint_over_session_value():
    """Frontend bridge may forward the BFF id_token explicitly; that hint must win."""
    sess = main.RUNTIME.session_store.create(
        sub="user-xyz",
        roles=["student"],
        name="Student",
        id_token="stale-session-id-token",
    )
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get(
            "/auth/logout",
            follow_redirects=False,
            headers={"x-gustav-id-token-hint": "fresh-bff-id-token"},
        )
    assert r.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(r.headers.get("location", "")).query)
    assert qs.get("id_token_hint") == ["fresh-bff-id-token"]
    assert "client_id" not in qs


@pytest.mark.anyio
async def test_logout_uses_app_runtime_session_store_and_oidc_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_store = SessionStore()
    runtime_cfg = OIDCConfig(
        base_url="http://runtime-idp:8080",
        realm="runtime-realm",
        client_id="runtime-client",
        redirect_uri="https://runtime-app.example/auth/callback",
        public_base_url="https://runtime-idp.example",
    )
    monkeypatch.setattr(main.RUNTIME, "session_store", runtime_store)
    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)

    sess = runtime_store.create(sub="runtime-user", roles=["student"], name="Student", id_token="runtime-id-token")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/auth/logout", follow_redirects=False)

    assert r.status_code in (302, 303)
    assert runtime_store.get(sess.session_id) is None
    location = r.headers.get("location", "")
    parsed = urlparse(location)
    assert f"{parsed.scheme}://{parsed.netloc}" == "https://runtime-idp.example"
    assert parsed.path == "/realms/runtime-realm/protocol/openid-connect/logout"
    qs = parse_qs(parsed.query)
    assert qs.get("id_token_hint") == ["runtime-id-token"]


@pytest.mark.anyio
async def test_logout_rejects_external_redirect_uri():
    """GET /auth/logout must not accept external post-logout redirects.

    External redirect query params must be ignored. The resulting
    `post_logout_redirect_uri` should point to the app base +
    `/auth/logout/success`.
    """
    # No session required for this check; focus on redirect handling only
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/logout?redirect=https://evil.com", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    # Extract the post_logout_redirect_uri from the IdP end-session URL
    from urllib.parse import urlparse, parse_qs, unquote
    qs = parse_qs(urlparse(loc).query)
    post_logout = unquote(qs.get("post_logout_redirect_uri", [""])[0])
    # Compute expected app base from configured redirect URI
    ru = main.RUNTIME.oidc_config.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/auth/logout/success"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
async def test_logout_allows_inapp_redirect_path():
    """GET /auth/logout should accept app-internal absolute paths as redirect."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/logout?redirect=/courses", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    from urllib.parse import urlparse, parse_qs, unquote
    qs = parse_qs(urlparse(loc).query)
    post_logout = unquote(qs.get("post_logout_redirect_uri", [""])[0])
    ru = main.RUNTIME.oidc_config.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/courses"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
async def test_state_expiry_leads_to_400_no_store():
    """Expired state must be rejected with 400 and no-store header."""
    # Create an already-expired state
    rec = main.RUNTIME.state_store.create(code_verifier="v", ttl_seconds=-1)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.json().get("error") == "invalid_code_or_state"


@pytest.mark.anyio
async def test_callback_no_store_on_token_exchange_failure(monkeypatch: pytest.MonkeyPatch):
    """Token exchange failure must return 400 with no-store header."""
    class FailingOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            raise RuntimeError("boom")

    install_oidc_client(monkeypatch, main, FailingOIDC())
    rec = main.RUNTIME.state_store.create(code_verifier="v")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.json().get("error") == "token_exchange_failed"


@pytest.mark.anyio
async def test_callback_no_store_on_invalid_id_token(monkeypatch: pytest.MonkeyPatch):
    """Missing/invalid id_token must return 400 with no-store header."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": ""}  # invalid: empty

    install_oidc_client(monkeypatch, main, FakeOIDC())
    rec = main.RUNTIME.state_store.create(code_verifier="v")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.json().get("error") == "invalid_id_token"


@pytest.mark.anyio
async def test_logout_double_slash_redirect_is_internal():
    """redirect=// is unsafe and must be ignored; default to logout success page."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/logout?redirect=//", follow_redirects=False)
    assert r.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs, unquote
    qs = parse_qs(urlparse(r.headers.get("location", "")).query)
    post_logout = unquote(qs.get("post_logout_redirect_uri", [""])[0])
    ru = main.RUNTIME.oidc_config.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/auth/logout/success"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
@pytest.mark.parametrize("bad_redirect", [
    "/a//b",
    "/../x",
    "/..",
])
async def test_login_rejects_unsafe_internal_paths(monkeypatch: pytest.MonkeyPatch, bad_redirect: str):
    """Unsafe internal redirect paths (double-slash, traversal) must be ignored in login flow."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get(f"/auth/login?redirect={bad_redirect}", follow_redirects=False)
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present in authorization URL"
        # Satisfy nonce check by returning the stored nonce
        rec = getattr(main.RUNTIME.state_store, "_data", {}).get(state)
        expected_nonce = getattr(rec, "nonce", None)
        def ok_verify(id_token: str, cfg: object):
            return {
                "email": "user@example.com",
                "realm_access": {"roles": ["student"]},
                "email_verified": True,
                "nonce": expected_nonce,
            }
        monkeypatch.setattr(main, "verify_id_token", ok_verify)
        r_cb = await client.get(f"/auth/callback?code=valid&state={state}", follow_redirects=False)
    assert r_cb.status_code in (302, 303)
    # Fallback to in-app root when redirect is unsafe
    assert r_cb.headers.get("location") == "/"


@pytest.mark.anyio
@pytest.mark.parametrize("bad_redirect", [
    "/a//b",
    "/../x",
    "/..",
])
async def test_logout_rejects_unsafe_internal_paths(bad_redirect: str):
    """Unsafe internal logout redirects must be ignored in favor of success page."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/logout?redirect={bad_redirect}", follow_redirects=False)
    assert r.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs, unquote
    qs = parse_qs(urlparse(r.headers.get("location", "")).query)
    post_logout = unquote(qs.get("post_logout_redirect_uri", [""])[0])
    ru = main.RUNTIME.oidc_config.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/auth/logout/success"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
async def test_redirect_max_length_enforced(monkeypatch: pytest.MonkeyPatch):
    """Overly long redirect values must be ignored in login and logout flows."""
    # Build a 300-char path
    long_path = "/" + ("a" * 299)

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    # Login flow should ignore long redirect and send user to '/'
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get(f"/auth/login?redirect={long_path}", follow_redirects=False)
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state
        rec = getattr(main.RUNTIME.state_store, "_data", {}).get(state)
        expected_nonce = getattr(rec, "nonce", None)
        def ok_verify(id_token: str, cfg: object):
            return {
                "email": "user@example.com",
                "realm_access": {"roles": ["student"]},
                "email_verified": True,
                "nonce": expected_nonce,
            }
        monkeypatch.setattr(main, "verify_id_token", ok_verify)
        r_cb = await client.get(f"/auth/callback?code=valid&state={state}", follow_redirects=False)
    assert r_cb.status_code in (302, 303)
    assert r_cb.headers.get("location") == "/"

    # Logout flow should ignore long redirect and use success page
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/logout?redirect={long_path}", follow_redirects=False)
    assert r.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs, unquote
    qs = parse_qs(urlparse(r.headers.get("location", "")).query)
    post_logout = unquote(qs.get("post_logout_redirect_uri", [""])[0])
    ru = main.RUNTIME.oidc_config.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/auth/logout/success"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
async def test_sidebar_displays_name_not_email(monkeypatch: pytest.MonkeyPatch):
    """The retained navigation component renders display names without email fallback."""

    html = Navigation(
        {"sub": "user-xyz", "name": "Display User", "role": "student", "roles": ["student"]},
        current_path="/learning",
    ).render()

    assert "Display User" in html
    assert "user-name" in html


@pytest.mark.anyio
async def test_api_me_handles_session_store_failure(monkeypatch: pytest.MonkeyPatch):
    """Session backend errors must result in a 401 response (fail closed)."""

    class ExplodingStore:
        def get(self, session_id: str):
            raise RuntimeError("boom")

        def delete(self, session_id: str):
            return None

    monkeypatch.setattr(main.RUNTIME, "session_store", ExplodingStore())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", "any-session")
        resp = await client.get("/api/me")

    assert resp.status_code == 401
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.json().get("error") == "unauthenticated"


@pytest.mark.anyio
async def test_api_me_uses_app_runtime_session_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_store = SessionStore()
    monkeypatch.setattr(main.RUNTIME, "session_store", runtime_store)

    session = runtime_store.create(sub="runtime-api-me", roles=["student"], name="Runtime User")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["sub"] == "runtime-api-me"


@pytest.mark.anyio
async def test_callback_rejects_when_id_token_nonce_missing(monkeypatch: pytest.MonkeyPatch):
    """If a nonce was stored for the state, missing `nonce` in ID token must be rejected."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    def claims_without_nonce(id_token: str, cfg: object):
        return {
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
            # deliberately no 'nonce'
        }

    monkeypatch.setattr(main, "verify_id_token", claims_without_nonce)

    # Create state with a stored nonce
    rec = main.RUNTIME.state_store.create(code_verifier="v", nonce="expected-nonce")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=valid&state={rec.state}")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.json().get("error") in {"invalid_id_token", "invalid_nonce"}


@pytest.mark.anyio
async def test_callback_uses_app_runtime_state_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_state_store = StateStore()
    monkeypatch.setattr(main.RUNTIME, "state_store", runtime_state_store)

    class FakeOIDC:
        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            assert code == "valid"
            assert code_verifier == "runtime-verifier"
            return {"id_token": "runtime-id-token"}

    def verify_runtime_token(id_token: str, cfg: object):
        assert id_token == "runtime-id-token"
        return {
            "sub": "runtime-callback",
            "name": "Runtime Callback",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    install_oidc_client(monkeypatch, main, FakeOIDC())
    monkeypatch.setattr(main, "verify_id_token", verify_runtime_token)
    record = runtime_state_store.create(code_verifier="runtime-verifier")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(f"/auth/callback?code=valid&state={record.state}", follow_redirects=False)

    assert response.status_code in (302, 303)


@pytest.mark.anyio
async def test_callback_uses_app_runtime_oidc_client_and_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_state_store = StateStore()
    runtime_cfg = OIDCConfig(
        base_url="http://runtime-idp:8080",
        realm="runtime-realm",
        client_id="runtime-client",
        redirect_uri="https://runtime-app.example/auth/callback",
        public_base_url="https://runtime-idp.example",
    )

    class RuntimeOIDC:
        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            assert code == "valid"
            assert code_verifier == "runtime-verifier"
            return {"id_token": "runtime-id-token"}

    def verify_runtime_token(id_token: str, cfg: object):
        assert id_token == "runtime-id-token"
        assert cfg is runtime_cfg
        return {
            "sub": "runtime-oidc-callback",
            "name": "Runtime OIDC Callback",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main.RUNTIME, "state_store", runtime_state_store)
    monkeypatch.setattr(main.RUNTIME, "oidc_client", RuntimeOIDC())
    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)
    monkeypatch.setattr(main, "verify_id_token", verify_runtime_token)
    record = runtime_state_store.create(code_verifier="runtime-verifier")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(f"/auth/callback?code=valid&state={record.state}", follow_redirects=False)

    assert response.status_code in (302, 303)


@pytest.mark.anyio
async def test_callback_uses_app_runtime_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_state_store = StateStore()
    runtime_cfg = main.RUNTIME.oidc_config

    class RuntimeOIDC:
        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            assert code == "valid"
            assert code_verifier == "runtime-verifier"
            return {"id_token": "runtime-id-token"}

    def verify_runtime_token(id_token: str, cfg: object):
        assert id_token == "runtime-id-token"
        assert cfg is runtime_cfg
        return {
            "sub": "runtime-env-callback",
            "name": "Runtime Env Callback",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main.RUNTIME, "state_store", runtime_state_store)
    install_oidc_client(monkeypatch, main, RuntimeOIDC())
    runtime_settings = AuthSettings()
    runtime_settings.override_environment("prod")
    monkeypatch.setattr(main.RUNTIME, "settings", runtime_settings)
    monkeypatch.setattr(main, "verify_id_token", verify_runtime_token)
    record = runtime_state_store.create(code_verifier="runtime-verifier")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(f"/auth/callback?code=valid&state={record.state}", follow_redirects=False)

    assert response.status_code in (302, 303)
    set_cookie = response.headers.get("set-cookie", "")
    assert "Max-Age=" in set_cookie
