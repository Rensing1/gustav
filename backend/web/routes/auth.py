"""
Authentication-related FastAPI routes (router-only module).

Why:
    Keep auth endpoints in a dedicated router to avoid duplication between the
    full app and the slim test app, and to improve maintainability.

Notes:
    - This module purposely imports from `main` inside functions to reuse the
      shared OIDC config, state/session stores, and cookie policy helpers.
      This keeps the state shared with `/auth/callback`, which remains defined
      in `main.py` for test monkeypatching compatibility.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from urllib.parse import urlencode, quote
import os
import secrets

from identity_access.oidc import OIDCClient


auth_router = APIRouter(tags=["auth"])  # explicit paths, no prefix


@auth_router.get("/auth/login")
async def auth_login(redirect: str | None = None):
    """
    Start OIDC flow with PKCE and server-side state; redirect to IdP.

    Behavior:
        - Generates code_verifier + S256 code_challenge.
        - Validates optional `redirect` to be an absolute in-app path; external
          URLs are rejected. Persists the validated redirect together with the
          server-generated state in a server-side store.
        - Redirects to Keycloak authorization endpoint.
    Permissions:
        Public.
    """
    import main  # late import to share STATE_STORE / OIDC_CFG

    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    nonce = secrets.token_urlsafe(16)
    # Security: Accept only absolute in-app paths like "/courses". Reject external URLs.
    safe_redirect = redirect if (isinstance(redirect, str) and _is_inapp_path(redirect)) else None
    rec = main.STATE_STORE.create(code_verifier=code_verifier, redirect=safe_redirect, nonce=nonce)
    final_state = rec.state
    # Use a fresh client bound to current config (allows monkeypatch in tests)
    oidc = OIDCClient(main.OIDC_CFG)
    url = oidc.build_authorization_url(state=final_state, code_challenge=code_challenge, nonce=nonce)
    return RedirectResponse(url=url, status_code=302)


@auth_router.get("/auth/forgot")
async def auth_forgot(login_hint: str | None = None):
    """
    Redirect to Keycloak 'Forgot Password' page.
    """
    import main  # late import

    base = f"{main.OIDC_CFG.base_url}/realms/{main.OIDC_CFG.realm}/login-actions/reset-credentials"
    query = {"login_hint": login_hint} if login_hint else None
    target = f"{base}?{urlencode(query)}" if query else base
    return RedirectResponse(url=target, status_code=302)


@auth_router.get("/auth/register")
async def auth_register(login_hint: str | None = None):
    """
    Redirect to Keycloak registration by hinting kc_action=register on the auth endpoint.

    Why:
        Keep registration on the IdP while ensuring the authorization request
        includes a fresh nonce (OIDC replay protection), same as the login flow.
    Permissions:
        Public.
    """
    import main  # late import

    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    # Phase 2: Generate nonce for replay protection and persist in state
    nonce = secrets.token_urlsafe(16)
    rec = main.STATE_STORE.create(code_verifier=code_verifier, redirect=None, nonce=nonce)
    final_state = rec.state
    oidc = OIDCClient(main.OIDC_CFG)
    # Include nonce in the authorization request similar to /auth/login
    url = oidc.build_authorization_url(state=final_state, code_challenge=code_challenge, nonce=nonce)
    sep = '&' if '?' in url else '?'
    if login_hint:
        # Security: encode parameter to avoid query injection and preserve special characters
        from urllib.parse import urlencode
        url = f"{url}{sep}{urlencode({'login_hint': login_hint})}"
        sep = '&'
    url = f"{url}{sep}kc_action=register"
    return RedirectResponse(url=url, status_code=302)


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
    """
    import main  # late import for stores and cookie policy

    # Remove server-side session if present
    sid = request.cookies.get(main.SESSION_COOKIE_NAME)
    rec = main.SESSION_STORE.get(sid or "") if sid else None
    if sid:
        main.SESSION_STORE.delete(sid)

    # Compute IdP logout URL and app redirect target (show success banner)
    base = (main.OIDC_CFG.public_base_url or main.OIDC_CFG.base_url).rstrip("/")
    app_base = _default_app_base(main.OIDC_CFG.redirect_uri)
    # Accept only in-app absolute paths; ignore external values
    safe_redirect = redirect if (isinstance(redirect, str) and _is_inapp_path(redirect)) else None
    # After logout, go to the app success page with a re-login link
    dest = (f"{app_base}{safe_redirect}" if safe_redirect else f"{app_base}/auth/logout/success").rstrip("/")
    # Build params: prefer id_token_hint (best compatibility), else include client_id
    end_session = f"{base}/realms/{main.OIDC_CFG.realm}/protocol/openid-connect/logout?post_logout_redirect_uri={quote(dest, safe=':/?&=')}"
    if rec and getattr(rec, "id_token", None):
        end_session += f"&id_token_hint={quote(rec.id_token)}"
    else:
        end_session += f"&client_id={quote(main.OIDC_CFG.client_id)}"

    resp = RedirectResponse(url=end_session, status_code=302)
    # Clear cookie consistent with environment flags
    opts = _cookie_opts()
    resp.set_cookie(
        key=main.SESSION_COOKIE_NAME,
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
    return HTMLResponse(content=html)


# Removed separate /auth/logout/idp — unified into GET /auth/logout


def _cookie_opts() -> dict:
    """Return cookie flags based on main.SETTINGS (dev/prod)."""
    import main  # late import

    env = main.SETTINGS.environment
    secure = env == "prod"
    samesite = "strict" if secure else "lax"
    return {"secure": secure, "samesite": samesite}


def _default_app_base(redirect_uri: str) -> str:
    """Compute app base (scheme+host+port) from configured redirect URI."""
    try:
        # Prefer removing trailing /auth/callback if present
        if "/auth/callback" in redirect_uri:
            return redirect_uri.split("/auth/callback")[0]
        # Else, strip path
        from urllib.parse import urlparse
        p = urlparse(redirect_uri)
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return "/"


def _is_inapp_path(value: str) -> bool:
    """Return True if value is an absolute in-app path, e.g., "/", "/courses/1".

    Why:
        Prevent open redirect vulnerabilities by only allowing internal paths
        without scheme/host or query fragments. Mirrors the OpenAPI contract.
    """
    try:
        if not value or not isinstance(value, str):
            return False
        import re
        return bool(re.match(r"^/[A-Za-z0-9_\-/]*$", value))
    except Exception:
        return False
