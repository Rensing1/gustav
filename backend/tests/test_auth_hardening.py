"""
Auth hardening tests (TDD: RED)

Covers:
- Client-supplied `state` is ignored (server-generated only)
- External redirects are rejected; fallback to "/"
- Callback 400 responses set Cache-Control: no-store
- SSR role display uses fixed priority (admin > teacher > student)
- Logout includes id_token_hint when available
"""

import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport

from identity_access.stores import SessionStore, SessionRecord  # type: ignore  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture(autouse=True)
def _force_dev_env():
    """Force dev env for deterministic cookie flags (secure off for http://test)."""
    main.SETTINGS.override_environment("dev")
    yield
    main.SETTINGS.override_environment(None)


def _latest_session_record() -> tuple[str, SessionRecord]:
    store = getattr(main, "SESSION_STORE", None)
    assert store, "SESSION_STORE must be configured"
    data = getattr(store, "_data", {})
    assert data, "SESSION_STORE should contain at least one entry"
    sid, rec = next(iter(data.items()))
    return sid, rec


def _ensure_cookie_with_current_session(client: httpx.AsyncClient) -> SessionRecord:
    if client.cookies.get("gustav_session"):
        sid = client.cookies.get("gustav_session")
        rec = main.SESSION_STORE.get(sid or "")
        assert rec, "Cookie references unknown session"
        return rec
    sid, rec = _latest_session_record()
    client.cookies.set("gustav_session", sid)
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
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    # Start login with external redirect attempt
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get("/auth/login?redirect=https://evil.com", follow_redirects=False)
        assert r_login.status_code in (302, 303)
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present in authorization URL"
        # Phase 2: extract stored nonce to satisfy nonce check
        rec = getattr(main.STATE_STORE, "_data", {}).get(state)
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
async def test_callback_errors_set_no_store_header():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Missing code/state
        r = await client.get("/auth/callback")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_role_priority_for_ssr_display(monkeypatch: pytest.MonkeyPatch):
    """SSR sidebar must display primary role by fixed priority (admin>teacher>student)."""
    # Create a session with roles in an order that would be ambiguous without priority
    sess = main.SESSION_STORE.create(sub="teacher-1", name="Frau Lehrerin", roles=["student", "teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/", follow_redirects=False)
    assert r.status_code == 200
    html = r.text
    # Expect German label for teacher (higher priority than student)
    assert "Lehrer" in html


@pytest.mark.anyio
async def test_logout_uses_id_token_hint_when_available(monkeypatch: pytest.MonkeyPatch):
    """If session contains an id_token, /auth/logout should include id_token_hint param."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token-123"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())
    monkeypatch.setattr(main, "verify_id_token", lambda id_token, cfg: {
        "email": "user@example.com",
        "realm_access": {"roles": ["student"]},
        "email_verified": True,
    })

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Create server-side session via callback first
        # Seed a valid state
        rec = main.STATE_STORE.create(code_verifier="v")
        r_cb = await client.get(f"/auth/callback?code=valid&state={rec.state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        rec = _ensure_cookie_with_current_session(client)
        assert rec.id_token, "Session record must carry the issued id_token"
        # Use the established session to call logout
        # httpx client kept cookies from redirect response
        r_lo = await client.get("/auth/logout", follow_redirects=False)
    assert r_lo.status_code in (302, 303)
    loc = r_lo.headers.get("location", "")
    assert "id_token_hint=" in loc


@pytest.mark.anyio
async def test_logout_without_session_only_sends_client_id(monkeypatch: pytest.MonkeyPatch):
    """When no session cookie is present, logout must not reuse prior id_token hints."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token-xyz"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    def ok_verify(id_token: str, cfg: object):
        return {
            "sub": "student-123",
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", ok_verify)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        rec = main.STATE_STORE.create(code_verifier="v")
        r_cb = await client.get(f"/auth/callback?code=valid&state={rec.state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        # Simulate client losing cookies before calling logout
        client.cookies.clear()
        r_lo = await client.get("/auth/logout", follow_redirects=False)
    assert r_lo.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(r_lo.headers.get("location", "")).query)
    # Without a session/id_token, logout must fall back to client_id only
    assert qs.get("client_id") == [main.OIDC_CFG.client_id]
    assert "id_token_hint" not in qs


@pytest.mark.anyio
async def test_logout_session_without_id_token_falls_back_to_client_id():
    """Sessions missing id_token must fall back to client_id instead of stale hints."""
    store = getattr(main, "SESSION_STORE")
    sess = store.create(sub="user-xyz", roles=["student"], name="Student", id_token=None)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/auth/logout", follow_redirects=False)
    assert r.status_code in (302, 303)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(r.headers.get("location", "")).query)
    assert qs.get("client_id") == [main.OIDC_CFG.client_id]
    assert "id_token_hint" not in qs


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
    ru = main.OIDC_CFG.redirect_uri
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
    ru = main.OIDC_CFG.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/courses"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
async def test_state_expiry_leads_to_400_no_store():
    """Expired state must be rejected with 400 and no-store header."""
    # Create an already-expired state
    rec = main.STATE_STORE.create(code_verifier="v", ttl_seconds=-1)
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
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            raise RuntimeError("boom")

    monkeypatch.setattr(main, "OIDC", FailingOIDC())
    rec = main.STATE_STORE.create(code_verifier="v")
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
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": ""}  # invalid: empty

    monkeypatch.setattr(main, "OIDC", FakeOIDC())
    rec = main.STATE_STORE.create(code_verifier="v")
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
    ru = main.OIDC_CFG.redirect_uri
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
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get(f"/auth/login?redirect={bad_redirect}", follow_redirects=False)
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present in authorization URL"
        # Satisfy nonce check by returning the stored nonce
        rec = getattr(main.STATE_STORE, "_data", {}).get(state)
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
    ru = main.OIDC_CFG.redirect_uri
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
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    # Login flow should ignore long redirect and send user to '/'
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get(f"/auth/login?redirect={long_path}", follow_redirects=False)
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state
        rec = getattr(main.STATE_STORE, "_data", {}).get(state)
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
    ru = main.OIDC_CFG.redirect_uri
    app_base = ru.split("/auth/callback")[0] if "/auth/callback" in ru else ru.rsplit("/", 1)[0]
    expected = f"{app_base}/auth/logout/success"
    assert post_logout.rstrip("/") == expected.rstrip("/")


@pytest.mark.anyio
async def test_sidebar_displays_name_not_email():
    """SSR sidebar should render the user's display name (not email)."""
    # Create a session with a specific display name
    sess = main.SESSION_STORE.create(sub="user-xyz", name="Alice Example", roles=["student"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/", follow_redirects=False)
    assert r.status_code == 200
    html = r.text
    assert "Alice Example" in html
    # Ensure the updated CSS hook is present for teaching clarity
    assert "user-name" in html


@pytest.mark.anyio
async def test_api_me_handles_session_store_failure(monkeypatch: pytest.MonkeyPatch):
    """Session backend errors must result in a 401 response (fail closed)."""

    class ExplodingStore:
        def get(self, session_id: str):
            raise RuntimeError("boom")

        def delete(self, session_id: str):
            return None

    monkeypatch.setattr(main, "SESSION_STORE", ExplodingStore())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", "any-session")
        resp = await client.get("/api/me")

    assert resp.status_code == 401
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.json().get("error") == "unauthenticated"


@pytest.mark.anyio
async def test_callback_rejects_when_id_token_nonce_missing(monkeypatch: pytest.MonkeyPatch):
    """If a nonce was stored for the state, missing `nonce` in ID token must be rejected."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    def claims_without_nonce(id_token: str, cfg: object):
        return {
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
            # deliberately no 'nonce'
        }

    monkeypatch.setattr(main, "verify_id_token", claims_without_nonce)

    # Create state with a stored nonce
    rec = main.STATE_STORE.create(code_verifier="v", nonce="expected-nonce")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=valid&state={rec.state}")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.json().get("error") in {"invalid_id_token", "invalid_nonce"}
