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
from fastapi.responses import RedirectResponse, Response
from urllib.parse import urlencode, quote
import os

from identity_access.oidc import OIDCClient


auth_router = APIRouter(tags=["auth"])  # explicit paths, no prefix


@auth_router.get("/auth/login")
async def auth_login(state: str | None = None, redirect: str | None = None):
    """
    Start OIDC flow with PKCE and server-side state; redirect to IdP.

    Behavior:
        - Generates code_verifier + S256 code_challenge.
        - Persists state with redirect in server-side store.
        - Redirects to Keycloak authorization endpoint.
    Permissions:
        Public.
    """
    import main  # late import to share STATE_STORE / OIDC_CFG

    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    rec = main.STATE_STORE.create(code_verifier=code_verifier, redirect=redirect)
    final_state = state or rec.state
    # Use a fresh client bound to current config (allows monkeypatch in tests)
    oidc = OIDCClient(main.OIDC_CFG)
    url = oidc.build_authorization_url(state=final_state, code_challenge=code_challenge)
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
    """
    import main  # late import

    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    rec = main.STATE_STORE.create(code_verifier=code_verifier, redirect=None)
    final_state = rec.state
    oidc = OIDCClient(main.OIDC_CFG)
    url = oidc.build_authorization_url(state=final_state, code_challenge=code_challenge)
    sep = '&' if '?' in url else '?'
    if login_hint:
        url = f"{url}{sep}login_hint={login_hint}"
        sep = '&'
    url = f"{url}{sep}kc_action=register"
    return RedirectResponse(url=url, status_code=302)


@auth_router.post("/auth/logout")
async def auth_logout(request: Request):
    """
    Invalidate server-side session and clear session cookie.
    """
    import main  # late import for stores and cookie policy

    if main.SESSION_COOKIE_NAME not in request.cookies:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sid = request.cookies.get(main.SESSION_COOKIE_NAME)
    if sid:
        main.SESSION_STORE.delete(sid)
    resp = Response(status_code=204)
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


@auth_router.get("/auth/logout/idp")
async def auth_logout_idp(redirect: str | None = None):
    """
    Optional: Redirect to IdP end-session endpoint to log out at Keycloak.

    Behavior:
        - Computes `post_logout_redirect_uri` (defaults to app base URL).
        - Redirects to `/protocol/openid-connect/logout` on the realm.
    Permissions:
        Public; relies on IdP session cookie in the browser.
    """
    import main  # late import

    base = (main.OIDC_CFG.public_base_url or main.OIDC_CFG.base_url).rstrip("/")
    # Derive app base from redirect_uri if not provided
    app_base = _default_app_base(main.OIDC_CFG.redirect_uri)
    dest = redirect or app_base
    end_session = f"{base}/realms/{main.OIDC_CFG.realm}/protocol/openid-connect/logout?post_logout_redirect_uri={quote(dest, safe=':/?&=')}"
    return RedirectResponse(url=end_session, status_code=302)


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

