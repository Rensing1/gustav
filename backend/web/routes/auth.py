"""
Authentication-related FastAPI routes (router-only module).

Why:
    Keep auth endpoints in a dedicated router to avoid duplication between the
    full app and the slim test app, and to improve maintainability.

Notes:
    - This module purposely resolves the active main module inside functions to
      reuse shared OIDC config and state/session stores. The `/auth/callback`
      handler itself is provided by `backend.web.auth_bridge`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response, HTMLResponse, JSONResponse
from urllib.parse import urlencode
import os
import secrets

from backend.identity_access.oidc import OIDCClient, OIDCConfig
from backend.web.auth_session import SESSION_COOKIE_NAME, session_cookie_options
import logging

from .redirects import safe_inapp_path


auth_router = APIRouter(tags=["Auth"])  # explicit paths, no prefix (align with OpenAPI)
logger = logging.getLogger("gustav.web.auth")


def _parse_allowed_registration_domains(raw: str | None) -> set[str]:
    """Parse ALLOWED_REGISTRATION_DOMAINS env var into a normalized set of domains.

    Intent:
        - Accept a comma-separated list like "@school.example, @example.org".
        - Normalize by trimming whitespace and lowercasing.
        - Ignore empty entries so accidental trailing commas are harmless.
    """
    if not raw:
        return set()
    items = [part.strip().lower() for part in str(raw).split(",")]
    return {item for item in items if item}


def _registration_domain_error_payload(allowed_domains: set[str]) -> dict[str, str]:
    """
    Build a consistent error payload for disallowed registration domains.

    Keeps messaging aligned across auth route, OpenAPI contract and tests.
    """
    base_detail = "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt."
    if allowed_domains:
        domains_str = ", ".join(sorted(allowed_domains))
        detail = f"{base_detail} Erlaubte Domains: {domains_str}"
    else:
        detail = base_detail
    return {"error": "invalid_email_domain", "detail": detail}


def _is_allowed_registration_email(email: str, allowed_domains: set[str]) -> bool:
    """Return True if the email's domain is in the allowed_domains set.

    Behavior:
        - Treat an empty allow-list as "no restriction" to keep defaults simple.
        - Perform a minimal email check: split on the last '@' and compare the
          domain part (including leading '@') in lowercase.
        - Invalid emails (no '@' or missing domain) are treated as disallowed.
    """
    if not allowed_domains:
        return True
    if not isinstance(email, str):
        return False
    normalized = email.strip().lower()
    if "@" not in normalized:
        return False
    local, domain = normalized.rsplit("@", 1)
    if not local or not domain:
        return False
    key = f"@{domain}"
    return key in allowed_domains


def _runtime_from_request(request: Request) -> object | None:
    """Return the explicit app runtime when the ASGI app provides one."""

    try:
        runtime = getattr(getattr(request, "app", None).state, "runtime", None)
    except Exception:
        return None
    return runtime


def _session_store(request: Request):
    """Return the app session store from the explicit app runtime."""

    runtime = _runtime_from_request(request)
    if runtime is not None and hasattr(runtime, "session_store"):
        return runtime.session_store
    raise RuntimeError("auth runtime session_store is not configured")


def _state_store(request: Request):
    """Return the OIDC state store from the explicit app runtime."""

    runtime = _runtime_from_request(request)
    if runtime is not None and hasattr(runtime, "state_store"):
        return runtime.state_store
    raise RuntimeError("auth runtime state_store is not configured")


def _oidc_config(request: Request):
    """Return OIDC configuration from the explicit app runtime."""

    runtime = _runtime_from_request(request)
    if runtime is not None and hasattr(runtime, "oidc_config"):
        return runtime.oidc_config
    raise RuntimeError("auth runtime oidc_config is not configured")


def _runtime_settings(request: Request):
    """Return auth settings from the explicit app runtime."""

    runtime = _runtime_from_request(request)
    if runtime is not None and hasattr(runtime, "settings"):
        return runtime.settings
    raise RuntimeError("auth runtime settings are not configured")


def _request_app_base(request: Request) -> str:
    """Derive the browser-facing app base from the incoming request.

    Honors trusted proxy headers when GUSTAV_TRUST_PROXY=true; otherwise uses
    ASGI's scheme/host. Returns scheme://host[:port].
    """
    import os
    trust_proxy = (os.getenv("GUSTAV_TRUST_PROXY", "false") or "").lower() == "true"
    scheme = (request.url.scheme or "http").lower()
    # Prefer ASGI-parsed host:port when not trusting proxy headers to avoid
    # Host header spoofing; fall back to Host for completeness.
    if request.url.hostname:
        if request.url.port:
            host = f"{request.url.hostname}:{request.url.port}"
        else:
            host = request.url.hostname
    else:
        host = request.headers.get("host") or ""
    if trust_proxy:
        xf_proto = (request.headers.get("x-forwarded-proto") or scheme).split(",")[0].strip()
        xf_host = (request.headers.get("x-forwarded-host") or host).split(",")[0].strip()
        scheme = (xf_proto or scheme).lower()
        host = xf_host or host
    return f"{scheme}://{host}"


def _hostport_from_url(url: str) -> str:
    """Return lowercased host[:port] from a URL string.

    Defensive parsing: falls back to empty string on errors.
    """
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        if p.hostname:
            host = p.hostname.lower()
            port = p.port
            return f"{host}:{port}" if port else host
    except Exception:
        pass
    return ""

def _origin_from_url(url: str) -> tuple[str, str]:
    """Return (scheme, host[:port]) from a URL string, lowercased.

    Used to decide whether we can safely derive redirect_uri from the current
    request without causing a redirect_uri mismatch during token exchange.
    """
    try:
        from urllib.parse import urlparse

        p = urlparse(url or "")
        return (str(p.scheme or "").lower(), _hostport_from_url(url))
    except Exception:
        return ("", "")


def _same_origin(url_a: str, url_b: str) -> bool:
    """Return True when both URLs share the same (scheme, host[:port])."""
    sa, ha = _origin_from_url(url_a)
    sb, hb = _origin_from_url(url_b)
    return bool(sa and ha and sb and hb and sa == sb and ha == hb)


@auth_router.get("/auth/login")
async def auth_login(request: Request, redirect: str | None = None):
    """
    Start OIDC flow with PKCE and server-side state; redirect to IdP.

    Behavior:
        - Generates code_verifier + S256 code_challenge.
        - Validates optional `redirect` to be an absolute in-app path; external
          URLs are rejected. Persists the validated redirect together with the
          server-generated state in a server-side store.
        - Redirects to Keycloak authorization endpoint.
        - Sets `Cache-Control: private, no-store` on the 302 response to
          prevent caching of sensitive redirects.
    Permissions:
        Public.
    """
    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    nonce = secrets.token_urlsafe(16)
    # Security: Accept only absolute in-app paths like "/courses". Reject external URLs.
    safe_redirect = safe_inapp_path(redirect)
    rec = _state_store(request).create(code_verifier=code_verifier, redirect=safe_redirect, nonce=nonce)
    final_state = rec.state
    # Use a fresh client bound to current config (allows runtime overrides in tests)
    # Prefer dynamic redirect_uri only when the current request host matches
    # the allowed app host (from WEB_BASE or configured redirect_uri).
    base_cfg = _oidc_config(request)
    current_base = _request_app_base(request).rstrip("/")
    dynamic_redirect_uri = f"{current_base}/auth/callback"

    allowed_base = (os.getenv("WEB_BASE") or getattr(base_cfg, "redirect_uri")).rstrip("/")
    # Only use the dynamic redirect URI when the request origin matches the
    # configured app origin. This avoids a common proxy pitfall where ASGI sees
    # `http://...` but the browser-facing URL is `https://...`, which would
    # break the authorization-code token exchange (redirect_uri mismatch).
    same_host = _same_origin(dynamic_redirect_uri, allowed_base)

    redirect_uri = dynamic_redirect_uri if same_host else getattr(base_cfg, "redirect_uri")
    cfg = OIDCConfig(
        base_url=getattr(base_cfg, "base_url"),
        realm=getattr(base_cfg, "realm"),
        client_id=getattr(base_cfg, "client_id"),
        redirect_uri=redirect_uri,
        public_base_url=getattr(base_cfg, "public_base_url"),
    )
    oidc = OIDCClient(cfg)
    url = oidc.build_authorization_url(state=final_state, code_challenge=code_challenge, nonce=nonce)
    headers = {"Cache-Control": "private, no-store", "Vary": "HX-Request"}
    if request.headers.get("HX-Request"):
        headers["HX-Redirect"] = url
        return Response(status_code=204, headers=headers)
    return RedirectResponse(url=url, status_code=302, headers=headers)


@auth_router.get("/auth/forgot")
async def auth_forgot(request: Request, login_hint: str | None = None):
    """
    Redirect to Keycloak 'Forgot Password' page.

    Security:
        Adds `Cache-Control: private, no-store` to avoid caching redirect
        responses by browsers or proxies.
    """
    # Use browser-facing base URL if configured to avoid mixed host issues behind proxies
    cfg = _oidc_config(request)
    base_cfg = getattr(cfg, "public_base_url", None) or getattr(cfg, "base_url", "")
    public_or_internal = str(base_cfg).rstrip("/")
    realm = getattr(cfg, "realm", "gustav")
    base = f"{public_or_internal}/realms/{realm}/login-actions/reset-credentials"
    query = {"login_hint": login_hint} if login_hint else None
    target = f"{base}?{urlencode(query)}" if query else base
    headers = {"Cache-Control": "private, no-store", "Vary": "HX-Request"}
    return RedirectResponse(url=target, status_code=302, headers=headers)


@auth_router.get("/auth/password")
async def auth_password(request: Request, redirect: str | None = None):
    """Redirect to Keycloak password update flow for the current user."""
    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    nonce = secrets.token_urlsafe(16)
    safe_redirect = safe_inapp_path(redirect) or "/profile"
    rec = _state_store(request).create(code_verifier=code_verifier, redirect=safe_redirect, nonce=nonce)
    final_state = rec.state

    base_cfg = _oidc_config(request)
    current_base = _request_app_base(request).rstrip("/")
    dynamic_redirect_uri = f"{current_base}/auth/callback"
    allowed_base = (os.getenv("WEB_BASE") or getattr(base_cfg, "redirect_uri")).rstrip("/")
    same_host = _same_origin(dynamic_redirect_uri, allowed_base)
    redirect_uri = dynamic_redirect_uri if same_host else getattr(base_cfg, "redirect_uri")

    cfg = OIDCConfig(
        base_url=getattr(base_cfg, "base_url"),
        realm=getattr(base_cfg, "realm"),
        client_id=getattr(base_cfg, "client_id"),
        redirect_uri=redirect_uri,
        public_base_url=getattr(base_cfg, "public_base_url"),
    )
    oidc = OIDCClient(cfg)
    url = oidc.build_authorization_url(state=final_state, code_challenge=code_challenge, nonce=nonce)
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}kc_action=UPDATE_PASSWORD"
    headers = {"Cache-Control": "private, no-store", "Vary": "HX-Request"}
    if request.headers.get("HX-Request"):
        headers["HX-Redirect"] = url
        return Response(status_code=204, headers=headers)
    return RedirectResponse(url=url, status_code=302, headers=headers)


@auth_router.get("/auth/register")
async def auth_register(request: Request, login_hint: str | None = None, redirect: str | None = None):
    """
    Redirect directly to Keycloak's OIDC self-registration endpoint.

    Why:
        Keep registration on the IdP while ensuring the authorization request
        includes a fresh nonce (OIDC replay protection), same as the login flow.
    Permissions:
        Public.
    Security:
        Adds `Cache-Control: private, no-store` to prevent caching.
    """
    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    # Phase 2: Generate nonce for replay protection and persist in state
    nonce = secrets.token_urlsafe(16)
    safe_redirect = safe_inapp_path(redirect)
    rec = _state_store(request).create(code_verifier=code_verifier, redirect=safe_redirect, nonce=nonce)
    final_state = rec.state
    # Use dynamic redirect_uri only for allowed hosts, else fallback to configured
    base_cfg = _oidc_config(request)
    current_base = _request_app_base(request).rstrip("/")
    dynamic_redirect_uri = f"{current_base}/auth/callback"
    allowed_base = (os.getenv("WEB_BASE") or getattr(base_cfg, "redirect_uri", "")).rstrip("/")
    same_host = _same_origin(dynamic_redirect_uri, allowed_base)
    redirect_uri = dynamic_redirect_uri if same_host else getattr(base_cfg, "redirect_uri", "")
    cfg = OIDCConfig(
        base_url=getattr(base_cfg, "base_url", ""),
        realm=getattr(base_cfg, "realm", ""),
        client_id=getattr(base_cfg, "client_id", ""),
        redirect_uri=redirect_uri,
        public_base_url=getattr(base_cfg, "public_base_url", None),
    )
    oidc = OIDCClient(cfg)
    # Include nonce in the authorization request similar to /auth/login
    url = oidc.build_registration_url(state=final_state, code_challenge=code_challenge, nonce=nonce)
    headers = {"Cache-Control": "private, no-store", "Vary": "HX-Request"}

    # Optional: environment-driven domain allow-list for self-service registration.
    raw_allowed = os.getenv("ALLOWED_REGISTRATION_DOMAINS")
    allowed_domains = _parse_allowed_registration_domains(raw_allowed)

    sep = "&" if "?" in url else "?"
    if login_hint:
        # When an allow-list is configured, reject disallowed or malformed emails early.
        if not _is_allowed_registration_email(login_hint, allowed_domains):
            # Keep error payload aligned with OpenAPI Error schema.
            payload = _registration_domain_error_payload(allowed_domains)
            return JSONResponse(status_code=400, content=payload, headers=headers)
        # Security: encode parameter to avoid query injection and preserve special characters
        from urllib.parse import urlencode

        url = f"{url}{sep}{urlencode({'login_hint': login_hint})}"
    if request.headers.get("HX-Request"):
        headers["HX-Redirect"] = url
        return Response(status_code=204, headers=headers)
    return RedirectResponse(url=url, status_code=302, headers=headers)


@auth_router.get("/auth/logout")
async def auth_logout(request: Request, redirect: str | None = None):
    """
    Unified logout: clear app session cookie and redirect to IdP end-session.

    Behavior:
        - Deletes server-side session if present.
        - Sends Set-Cookie to expire the app session cookie.
        - Redirects (302) to Keycloak `end_session_endpoint` with
          `post_logout_redirect_uri` pointing back to the app (success page by default).
        - Accepts only in-app absolute paths for `redirect` (e.g., "/courses").
          External URLs are rejected/ignored to prevent open redirects.
    Permissions:
        Public; IdP end-session relies on IdP browser cookie.
    Security:
        Adds `Cache-Control: private, no-store` to the 302 response.
    """
    store = _session_store(request)

    # Remove server-side session if present (best-effort; never fail logout)
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    # Fallback: if framework cookie parser missed it (e.g., jar quirk), parse raw header
    if not sid:
        raw_cookie = request.headers.get("cookie", "")
        try:
            # Minimal, dependency-free parse for `gustav_session=<value>` token
            parts = [p.strip() for p in raw_cookie.split(";") if p]
            for p in parts:
                if p.startswith(f"{SESSION_COOKIE_NAME}="):
                    sid = p.split("=", 1)[1]
                    break
        except Exception:
            sid = None
    rec = None
    if sid:
        try:
            rec = store.get(sid or "")
        except Exception as exc:
            logger.warning("Session lookup failed during logout: %s", exc.__class__.__name__)
        try:
            store.delete(sid)
        except Exception as exc:
            logger.warning("Session delete failed during logout: %s", exc.__class__.__name__)

    # Compute IdP logout URL and app redirect target (show success banner)
    end_session = "/auth/logout/success"  # conservative fallback
    try:
        cfg = _oidc_config(request)
        base = (getattr(cfg, "public_base_url", None) or getattr(cfg, "base_url", "")).rstrip("/")
        app_base = _default_app_base(getattr(cfg, "redirect_uri", ""))
        # Accept only in-app absolute paths; ignore external values
        safe_redirect = safe_inapp_path(redirect)
        # After logout, go to the app success page with a re-login link
        dest = (f"{app_base}{safe_redirect}" if safe_redirect else f"{app_base}/auth/logout/success").rstrip("/")
        # Build params: prefer a forwarded BFF logout hint, then stored app-session
        # state, and only fall back to client_id when no ID token is available.
        params = {"post_logout_redirect_uri": dest}
        id_tok = (request.headers.get("x-gustav-id-token-hint") or "").strip() or None
        if not id_tok and rec and getattr(rec, "id_token", None):
            id_tok = rec.id_token
        if not id_tok:
            try:
                id_tok = getattr(getattr(request, "state", object()), "id_token", None)
            except Exception:
                id_tok = None
        if id_tok:
            params["id_token_hint"] = id_tok
        else:
            params["client_id"] = getattr(cfg, "client_id", "gustav-web")
        end_session = (
            f"{base}/realms/{getattr(cfg, 'realm', 'gustav')}/protocol/openid-connect/logout?" + urlencode(params)
        )
    except Exception as exc:
        logger.warning("Logout URL composition failed: %s", exc.__class__.__name__)

    resp = RedirectResponse(url=end_session, status_code=302)
    resp.headers["Cache-Control"] = "private, no-store"
    # Clear cookie consistent with environment flags.
    opts = session_cookie_options(_runtime_settings(request).environment)
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        httponly=True,
        secure=opts["secure"],
        samesite=opts["samesite"],
        path="/",
        expires=0,
        max_age=0,
    )
    return resp


@auth_router.get("/auth/logout/success", response_class=HTMLResponse)
async def auth_logout_success():
    """Render a minimal success page after logout with a link to /auth/login.

    Public page (allowlisted by middleware). No user data is displayed.
    Security: Include `Cache-Control: private, no-store`.
    """
    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Abgemeldet - GUSTAV</title>
      <link rel="stylesheet" href="/static/css/gustav.css" />
    </head>
    <body class="auth-info">
      <main class="container" style="max-width: 640px; margin: 10vh auto; background: var(--color-bg-surface); padding: 24px; border: 1px solid var(--color-border); border-radius: 8px;">
        <h1>Erfolgreich abgemeldet</h1>
        <p>Du wurdest von GUSTAV und dem Anmeldedienst abgemeldet.</p>
        <p>
          <a class="button button--primary" href="/auth/login">Erneut anmelden</a>
        </p>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(content=html, headers={"Cache-Control": "private, no-store"})


# Removed separate /auth/logout/idp — unified into GET /auth/logout


# Deprecated cookie helper removed; use `auth_utils.cookie_opts` directly


def _default_app_base(redirect_uri: str) -> str:
    """Compute the absolute application base URL from a redirect URI.

    Why:
        Keycloak's end-session flow requires an absolute `post_logout_redirect_uri`.
        This helper extracts `scheme://host[:port]` from the configured
        `REDIRECT_URI`. It is tolerant to malformed values and falls back to a
        sensible local default.

    Behavior:
        - If `redirect_uri` ends with `/auth/callback`, return the prefix before it.
        - Else, return `scheme://netloc` from parsing `redirect_uri`.
        - On parsing issues, try environment fallbacks; finally use
          `https://app.localhost`.
    """
    from urllib.parse import urlparse
    import os

    # 1) Common case: strip /auth/callback suffix
    if isinstance(redirect_uri, str) and "/auth/callback" in redirect_uri:
        prefix = redirect_uri.split("/auth/callback")[0]
        parsed = urlparse(prefix)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    # 2) Generic parse
    try:
        parsed = urlparse(redirect_uri)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass

    # 3) Environment fallbacks
    for var in ("APP_BASE", "WEB_BASE", "REDIRECT_URI"):
        val = os.getenv(var)
        if not val:
            continue
        try:
            p = urlparse(val)
            if "/auth/callback" in val:
                base = val.split("/auth/callback")[0]
                p2 = urlparse(base)
                if p2.scheme and p2.netloc:
                    return f"{p2.scheme}://{p2.netloc}"
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            continue

    # 4) Last resort: safe local default for dev
    return "https://app.localhost"
