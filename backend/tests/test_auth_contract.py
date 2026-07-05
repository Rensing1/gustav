"""
Auth contract tests (RED phase)

These tests assert the behavior defined in api/openapi.yml for the minimal
authentication slice (login, callback, logout, me, forgot). External IdP
interactions (Keycloak) are not performed here; we only assert HTTP contracts.
"""

import base64
import importlib
from http.cookies import SimpleCookie

import pytest
import httpx
from httpx import ASGITransport
import time
from typing import Dict, Callable
from jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import types
import requests
import yaml

from backend.tests.runtime_auth_helpers import install_oidc_client, install_oidc_config, install_session_store, install_state_store

TEST_ISSUER = "http://keycloak:8080/realms/gustav"
TEST_AUDIENCE = "gustav-web"
TEST_KID = "gustav-test-key"


def _install_oidc_config(monkeypatch: pytest.MonkeyPatch, main_module: object, cfg: object) -> None:
    install_oidc_config(monkeypatch, main_module, cfg)


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


# Generate an ephemeral RSA keypair per test run. This keeps the repo free of
# PEM blocks that secret scanners might flag as real credentials.
_TEST_RSA_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PRIVATE_KEY_PEM = _TEST_RSA_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")

_public_numbers = _TEST_RSA_PRIVATE_KEY.public_key().public_numbers()
TEST_JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": TEST_KID,
            "n": _b64url_uint(_public_numbers.n),
            "e": _b64url_uint(_public_numbers.e),
        }
    ]
}


def _make_id_token(
    claim_overrides: Dict[str, object] | None = None,
    header_overrides: Dict[str, object] | None = None,
) -> str:
    """Build a signed RS256 ID token for tests."""
    now = int(time.time())
    claims: Dict[str, object] = {
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "sub": "123456",
        "exp": now + 300,
        "iat": now,
        "email": "student@school.example",
        "preferred_username": "student",
        "realm_access": {"roles": ["student"]},
        "email_verified": True,
    }
    if claim_overrides:
        claims.update(claim_overrides)
    headers = {"kid": TEST_KID, "typ": "JWT"}
    if header_overrides:
        headers.update(header_overrides)
    return jwt.encode(claims, TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers=headers)


def _make_invalid_signature_token() -> str:
    valid = _make_id_token()
    parts = valid.split(".")
    tampered_signature = "invalidsig"
    return ".".join(parts[:2] + [tampered_signature])


async def _call_auth_callback_with_token(
    monkeypatch: pytest.MonkeyPatch,
    id_token: str,
    *,
    expected_status: int,
    configure: Callable[[object, object, object], None] | None = None,
    requests_get_override: Callable[[str, int], object] | None = None,
) -> httpx.Response:
    """
    Helper to exercise the real auth callback endpoint with a controlled ID token.
    """
    # Import lazily to avoid circulars during collection
    full_app = main.app
    from backend.identity_access.oidc import OIDCConfig
    from backend.identity_access.stores import StateStore

    # Fresh in-memory stores per run to avoid leakage between tests
    state_store = StateStore()
    install_state_store(monkeypatch, main, state_store)
    session_store = install_session_store(monkeypatch, main)
    test_cfg = OIDCConfig(
        base_url="http://keycloak:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)

    record = state_store.create(code_verifier="verifier-for-test")

    if configure is not None:
        configure(record, state_store, session_store)

    class FakeOIDC:
        def __init__(self, id_token: str):
            self.id_token = id_token
            self.cfg = test_cfg

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            assert code == "valid-code"
            assert code_verifier == "verifier-for-test"
            return {
                "access_token": "fake-access",
                "refresh_token": "fake-refresh",
                "id_token": self.id_token,
            }

    fake_client = FakeOIDC(id_token)
    install_oidc_client(monkeypatch, main, fake_client)

    # Reset JWKS cache for deterministic tests (no effect until verification module exists)
    try:
        from backend.identity_access import tokens as tokens_module  # type: ignore
    except ImportError:
        tokens_module = None
    if tokens_module and hasattr(tokens_module, "JWKSCache"):
        cache = tokens_module.JWKSCache(ttl_seconds=0)
        monkeypatch.setattr(tokens_module, "JWKS_CACHE", cache)

    # Stub JWKS retrieval (future implementation will call requests.get)
    if requests_get_override is None:
        def fake_requests_get(url: str, timeout: int = 5):
            return types.SimpleNamespace(
                status_code=200,
                json=lambda: TEST_JWKS,
            )

        monkeypatch.setattr("requests.get", fake_requests_get, raising=False)
    else:
        monkeypatch.setattr("requests.get", requests_get_override, raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as client:
        resp = await client.get(f"/auth/callback?code=valid-code&state={record.state}", follow_redirects=False)
    assert resp.status_code == expected_status
    return resp

# Import auth-only app factory to keep tests lean
main = importlib.import_module("backend.web.main")
create_app_auth_only = main.create_app_auth_only

# Force anyio to use asyncio backend only to avoid trio parametrization
pytestmark = pytest.mark.anyio("asyncio")


def is_redirect(status: int) -> bool:
    return status in (302, 303, 307, 308)


@pytest.mark.anyio
async def test_login_redirect():
    # Given: not authenticated (no cookie)
    # When: GET /auth/login
    app = main.create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/login", follow_redirects=False)
    # Then: 302 Redirect to Keycloak (contract)
    assert resp.status_code == 302
    assert "location" in resp.headers


@pytest.mark.anyio
async def test_login_dynamic_redirect_respects_whitelist(monkeypatch: pytest.MonkeyPatch):
    """When Host matches WEB_BASE/redirect_uri host, use dynamic redirect_uri."""
    from backend.identity_access.oidc import OIDCConfig
    from urllib.parse import urlparse, parse_qs

    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as client:
        # Simulate request on the allowed host
        resp = await client.get("/auth/login", follow_redirects=False, headers={"Host": "app.localhost:8100"})

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    u = urlparse(loc)
    qs = parse_qs(u.query)
    assert qs.get("redirect_uri") == ["http://app.localhost:8100/auth/callback"]


@pytest.mark.anyio
async def test_login_dynamic_redirect_falls_back_on_mismatch(monkeypatch: pytest.MonkeyPatch):
    """When Host differs, fall back to configured redirect_uri (avoid IdP errors)."""
    from backend.identity_access.oidc import OIDCConfig
    from urllib.parse import urlparse, parse_qs

    static_redirect = "http://app.localhost:8100/auth/callback"
    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri=static_redirect,
    )
    _install_oidc_config(monkeypatch, main, test_cfg)
    # Intentionally set WEB_BASE to allowed app host
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://evil.localhost:8100") as client:
        # Simulate request from a different host -> must not echo back
        resp = await client.get("/auth/login", follow_redirects=False, headers={"Host": "evil.localhost:8100"})

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    u = urlparse(loc)
    qs = parse_qs(u.query)
    assert qs.get("redirect_uri") == [static_redirect]


@pytest.mark.anyio
async def test_forgot_redirect():
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot", follow_redirects=False)
    assert resp.status_code == 302
    assert "location" in resp.headers


@pytest.mark.anyio
async def test_forgot_redirect_uses_oidc_cfg(monkeypatch: pytest.MonkeyPatch):
    """Forgot redirect should be built from the configured base_url + realm."""
    from backend.identity_access.oidc import OIDCConfig

    # Given OIDC configuration with custom base URL/realm
    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="school",
        client_id="gustav-web",
        redirect_uri="http://localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert loc.startswith("http://kc.example:8080/realms/school/login-actions/reset-credentials")


@pytest.mark.anyio
async def test_forgot_redirect_prefers_public_base_url(monkeypatch: pytest.MonkeyPatch):
    """Forgot redirect should use KC_PUBLIC_BASE_URL when provided."""
    from backend.identity_access.oidc import OIDCConfig

    test_cfg = OIDCConfig(
        base_url="http://kc.internal:8080",
        public_base_url="http://kc.public:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert loc.startswith("http://kc.public:8080/realms/gustav/login-actions/reset-credentials")


@pytest.mark.anyio
async def test_forgot_redirect_forwards_login_hint(monkeypatch: pytest.MonkeyPatch):
    """Forgot redirect forwards login_hint as query param."""
    from backend.identity_access.oidc import OIDCConfig
    from urllib.parse import urlparse, parse_qs

    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="school",
        client_id="gustav-web",
        redirect_uri="http://localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot?login_hint=student%40example.com", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    url = urlparse(loc)
    assert url.path.endswith("/realms/school/login-actions/reset-credentials")
    qs = parse_qs(url.query)
    assert qs.get("login_hint") == ["student@example.com"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code,state",
    [
        ("valid-code", "opaque-state"),
    ],
)
async def test_callback_success_redirects_and_sets_cookie(code: str, state: str):
    # When: GET /auth/callback with a (mock) valid code and state
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/auth/callback?code={code}&state={state}", follow_redirects=False)
    # Then: 302 + both headers present (strict per contract)
    assert resp.status_code == 302
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "location" in resp.headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code,state",
    [
        ("", "opaque"),
        ("invalid", ""),
        ("invalid", "invalid"),
    ],
)
async def test_callback_invalid_returns_400(code: str, state: str):
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/auth/callback?code={code}&state={state}")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_callback_rejects_expired_id_token(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({"exp": int(time.time()) - 10})
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=400)
    assert resp.json().get("error") == "invalid_id_token"


@pytest.mark.anyio
async def test_callback_rejects_wrong_issuer(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({"iss": "http://attack.example/realm"})
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=400)
    assert resp.json().get("error") == "invalid_id_token"


@pytest.mark.anyio
async def test_callback_rejects_wrong_audience(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({"aud": "other-client"})
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=400)
    assert resp.json().get("error") == "invalid_id_token"


@pytest.mark.anyio
async def test_callback_rejects_invalid_signature(monkeypatch: pytest.MonkeyPatch):
    token = _make_invalid_signature_token()
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=400)
    assert resp.json().get("error") == "invalid_id_token"


@pytest.mark.anyio
async def test_callback_accepts_valid_id_token(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token()
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=302)
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie


@pytest.mark.anyio
async def test_callback_filters_unknown_roles(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({"realm_access": {"roles": ["student", "teacher", "club-lead"]}})
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=302)
    cookie_header = resp.headers.get("set-cookie", "")
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session_id = cookie["gustav_session"].value

    import backend.web.main as main  # type: ignore  # noqa: E402

    stored = main.RUNTIME.session_store.get(session_id)
    assert stored is not None
    assert stored.roles == ["student", "teacher"]


@pytest.mark.anyio
async def test_callback_defaults_to_student_when_roles_missing(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({"realm_access": {}})
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=302)
    cookie_header = resp.headers.get("set-cookie", "")
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session_id = cookie["gustav_session"].value

    import backend.web.main as main  # type: ignore  # noqa: E402

    stored = main.RUNTIME.session_store.get(session_id)
    assert stored is not None
    assert stored.roles == ["student"]


@pytest.mark.anyio
async def test_callback_handles_jwks_fetch_failure(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token()

    def failing_requests_get(url: str, timeout: int = 5):
        raise requests.RequestException("jwks unreachable")

    resp = await _call_auth_callback_with_token(
        monkeypatch,
        token,
        expected_status=400,
        requests_get_override=failing_requests_get,
    )
    assert resp.json().get("error") == "invalid_id_token"


@pytest.mark.anyio
async def test_callback_rejects_expired_state(monkeypatch: pytest.MonkeyPatch):
    def configure(record, *_):
        monkeypatch.setattr("backend.identity_access.stores._now", lambda: record.expires_at + 1)

    token = _make_id_token()
    resp = await _call_auth_callback_with_token(
        monkeypatch,
        token,
        expected_status=400,
        configure=configure,
    )
    assert resp.json().get("error") == "invalid_code_or_state"


@pytest.mark.anyio
async def test_api_me_returns_401_after_session_expired(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token()
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=302)

    cookie_header = resp.headers.get("set-cookie", "")
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session_id = cookie["gustav_session"].value

    import backend.web.main as main  # type: ignore  # noqa: E402

    record = main.RUNTIME.session_store.get(session_id)
    assert record is not None
    assert record.expires_at is not None
    future = record.expires_at + 1

    monkeypatch.setattr("backend.identity_access.stores._now", lambda: future)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session_id)
        resp_me = await client.get("/api/me")
    assert resp_me.status_code == 401
    assert resp_me.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_callback_sets_secure_cookie_flags_in_prod(monkeypatch: pytest.MonkeyPatch):
    def configure(*_):
        import backend.web.main as main  # type: ignore  # noqa: E402
        monkeypatch.setattr(main.RUNTIME.settings, "_env_override", "prod", raising=False)

    token = _make_id_token()
    resp = await _call_auth_callback_with_token(
        monkeypatch,
        token,
        expected_status=302,
        configure=configure,
    )
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie


@pytest.mark.anyio
async def test_logout_uses_secure_cookie_flags_in_prod(monkeypatch: pytest.MonkeyPatch):
    def configure(*_):
        import backend.web.main as main  # type: ignore  # noqa: E402
        monkeypatch.setattr(main.RUNTIME.settings, "_env_override", "prod", raising=False)

    token = _make_id_token()
    resp = await _call_auth_callback_with_token(
        monkeypatch,
        token,
        expected_status=302,
        configure=configure,
    )
    cookie_header = resp.headers.get("set-cookie", "")
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session_id = cookie["gustav_session"].value

    import backend.web.main as main  # type: ignore  # noqa: E402

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session_id)
        resp_logout = await client.get("/auth/logout", follow_redirects=False)

    # Unified logout: 302 redirect to IdP end-session and clear cookie
    assert resp_logout.status_code in (301, 302, 303)
    set_cookie = resp_logout.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie


@pytest.mark.anyio
async def test_me_unauthenticated_returns_401():
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me")
    assert resp.status_code == 401
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_logout_requires_authentication():
    # Unified logout: even without app session cookie, GET /auth/logout redirects to IdP end-session
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)


@pytest.mark.anyio
async def test_logout_clears_cookie():
    # With a (fake) session cookie, logout should clear it
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("gustav_session", "fake-session")
        resp = await client.get("/auth/logout", follow_redirects=False)
    # Unified logout: redirect to IdP + clear cookie
    assert resp.status_code in (301, 302, 303)
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


@pytest.mark.anyio
async def test_me_authenticated_returns_200_and_new_shape():
    # With a (fake) session cookie, /api/me should return new DTO shape
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("gustav_session", "fake-session")
        resp = await client.get("/api/me")
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "private, no-store"
    body = resp.json()
    assert isinstance(body, dict)
    # New contract: sub, roles, name, expires_at
    assert "sub" in body and isinstance(body["sub"], str)
    assert "roles" in body and isinstance(body["roles"], list)
    assert "name" in body and isinstance(body["name"], str)
    assert "expires_at" in body and (body["expires_at"] is None or isinstance(body["expires_at"], str))
    # No email anymore
    assert "email" not in body


def test_openapi_contains_auth_paths():
    # Sanity check that contract includes expected paths
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    yml = (root / "api" / "openapi.yml").read_text(encoding="utf-8")
    for p in [
        "/auth/login",
        "/auth/callback",
        "/auth/logout",
        "/auth/logout/success",
        "/auth/forgot",
        "/auth/register",
        "/api/me",
    ]:
        assert p in yml


def test_openapi_me_schema_allows_nullable_expires_at():
    """Contract must document that expires_at may be null (session with no expiry)."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    yml = (root / "api" / "openapi.yml").read_text(encoding="utf-8")
    spec = yaml.safe_load(yml)
    expires_schema = spec["components"]["schemas"]["Me"]["properties"]["expires_at"]
    assert expires_schema.get("nullable") is True


def test_openapi_me_includes_401_response():
    """Contract should include 401 for unauthenticated /api/me calls."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    yml = (root / "api" / "openapi.yml").read_text(encoding="utf-8")
    spec = yaml.safe_load(yml)
    responses = spec["paths"]["/api/me"]["get"]["responses"]
    assert "401" in responses


@pytest.mark.anyio
async def test_register_redirect():
    # Slim app: ensure endpoint exists and redirects
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/register", follow_redirects=False)
    assert resp.status_code == 302
    assert "location" in resp.headers


@pytest.mark.anyio
async def test_register_redirect_uses_oidc_cfg(monkeypatch: pytest.MonkeyPatch):
    """Registration redirect should be built from the configured base_url + realm."""
    from backend.identity_access.oidc import OIDCConfig

    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="school",
        client_id="gustav-web",
        redirect_uri="http://localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    # We now use the standard auth endpoint with OIDC PKCE and hint register screen
    assert loc.startswith("http://kc.example:8080/realms/school/protocol/openid-connect/auth")
    assert "kc_action=register" in loc


@pytest.mark.anyio
async def test_register_redirect_forwards_login_hint(monkeypatch: pytest.MonkeyPatch):
    from backend.identity_access.oidc import OIDCConfig
    from urllib.parse import urlparse, parse_qs

    # Ensure allow-listing does not interfere with the happy-path redirect contract
    monkeypatch.delenv("ALLOWED_REGISTRATION_DOMAINS", raising=False)

    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="school",
        client_id="gustav-web",
        redirect_uri="http://localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, main, test_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=new%40example.com", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    url = urlparse(loc)
    assert url.path.endswith("/realms/school/protocol/openid-connect/auth")
    qs = parse_qs(url.query)
    assert qs.get("login_hint") == ["new@example.com"]
    assert qs.get("kc_action") == ["register"]


@pytest.mark.anyio
async def test_register_callback_redirects_to_safe_in_app_target(monkeypatch: pytest.MonkeyPatch):
    import backend.web.main as main  # type: ignore  # noqa: E402
    from urllib.parse import parse_qs, urlparse

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            assert code == "valid"
            assert code_verifier
            return {"id_token": "fake-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        register_response = await client.get(
            "/auth/register?login_hint=new%40school.example&redirect=/teaching/courses/course-1",
            follow_redirects=False,
        )

        assert register_response.status_code == 302
        location = register_response.headers.get("location", "")
        state = parse_qs(urlparse(location).query).get("state", [None])[0]
        assert state, "state must be present in registration redirect"

        rec = getattr(main.RUNTIME.state_store, "_data", {}).get(state)
        assert rec is not None
        assert rec.redirect == "/teaching/courses/course-1"

        expected_nonce = getattr(rec, "nonce", None)

        def fake_verify(id_token: str, cfg: object):
            return {
                "sub": "123456",
                "email": "new@school.example",
                "realm_access": {"roles": ["student"]},
                "email_verified": True,
                "nonce": expected_nonce,
            }

        monkeypatch.setattr(main, "verify_id_token", fake_verify)

        callback_response = await client.get(f"/auth/callback?code=valid&state={state}", follow_redirects=False)

    assert callback_response.status_code == 302
    assert callback_response.headers.get("location") == "/teaching/courses/course-1"


@pytest.mark.anyio
async def test_callback_sets_cookie_flags_and_no_max_age(monkeypatch: pytest.MonkeyPatch):
    """Cookie must be HttpOnly; SameSite=lax; Secure; no Max-Age (session)."""
    token = _make_id_token()
    resp = await _call_auth_callback_with_token(monkeypatch, token, expected_status=302)
    sc = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in sc
    assert "HttpOnly" in sc
    assert "SameSite=lax" in sc
    assert "Secure" in sc
    assert "Max-Age=" not in sc and "max-age=" not in sc
