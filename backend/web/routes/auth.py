"""Browser OIDC adapter: one flow repository and one GUSTAV session.

Synchronous endpoints run in FastAPI's thread pool. Neither the event loop nor
an open database transaction waits for the identity provider's network calls.
"""
from __future__ import annotations

import secrets
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.identity_access.oidc import OIDCClient
from backend.identity_access.session_tokens import session_values
from backend.identity_access.unified_sessions import SessionInvalid
from backend.web.auth_cookies import (
    ATTEMPT_COOKIE,
    BROWSER_COOKIE,
    LOGOUT_COOKIE,
    cookie,
    marker,
    valid_marker,
)
from backend.web.auth_session import SESSION_COOKIE_NAME
from backend.web.routes.redirects import safe_inapp_path
from backend.web.routes.security import cookie_origin_allowed

auth_router = APIRouter(tags=['Auth'])
HEADERS = {'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer'}


def _redirect(url):
    return RedirectResponse(url, status_code=302, headers=HEADERS)


def _error(request: Request, status: int, category: str):
    # Browser presentation lives in SvelteKit; never forward the callback's query.
    if 'text/html' in request.headers.get('accept', ''):
        return _redirect('/auth/problem?' + urlencode({'reason': category}))
    return JSONResponse({'error': category}, status_code=status, headers=HEADERS)


def _fallback(target, reason='login'):
    return _redirect('/?' + urlencode({'redirect': target or '/', 'reason': reason}))


def _start(request: Request, mode: str, target: str | None):
    runtime = request.app.state.runtime
    browser = request.cookies.get(BROWSER_COOKIE) or secrets.token_urlsafe(32)
    verifier = OIDCClient.generate_code_verifier()
    nonce = secrets.token_urlsafe(32)
    try:
        flow = runtime.session_repository.create_flow(browser=browser, mode=mode,
            redirect=safe_inapp_path(target), code_verifier=verifier, nonce=nonce)
    except Exception:
        return _error(request, 503, 'auth_unavailable')
    build = runtime.oidc_client.build_registration_url if mode == 'register' else runtime.oidc_client.build_authorization_url
    url = build(state=flow.state, code_challenge=OIDCClient.code_challenge_s256(verifier), nonce=nonce)
    if mode == 'continue':
        url += '&prompt=none'
    if mode == 'password':
        url += '&kc_action=UPDATE_PASSWORD'
    theme = request.cookies.get('gustav_theme')
    if theme in ('dark', 'light'):
        url += '&' + urlencode({'gustav_theme': theme})
    response = _redirect(url)
    cookie(response, BROWSER_COOKIE, browser, 900)
    if mode == 'continue':
        cookie(response, ATTEMPT_COOKIE, marker('attempt'), 60)
    else:
        cookie(response, LOGOUT_COOKIE, '', 0)
    return response


@auth_router.get('/auth/login')
def auth_login(request: Request, redirect: str | None = None):
    return _start(request, 'login', redirect)


@auth_router.get('/auth/register')
def auth_register(request: Request, redirect: str | None = None):
    """Open the IdP form immediately; Keycloak enforces registration domains."""
    return _start(request, 'register', redirect)


@auth_router.get('/auth/password')
def auth_password(request: Request, redirect: str | None = None):
    return _start(request, 'password', redirect or '/profile')


@auth_router.get('/auth/forgot')
def auth_forgot(request: Request, redirect: str | None = None, login_hint: str | None = None):
    response = _start(request, 'login', redirect or '/')
    if '/protocol/openid-connect/auth?' in response.headers.get('location', ''):
        # The OIDC reset entry preserves state, nonce and PKCE; login-actions does not.
        response.headers['location'] = response.headers['location'].replace('/protocol/openid-connect/auth?', '/protocol/openid-connect/forgot-credentials?')
        if login_hint:
            response.headers['location'] += '&' + urlencode({'login_hint': login_hint})
    return response


@auth_router.get('/auth/continue')
def auth_continue(request: Request, redirect: str | None = None):
    """Try silent SSO at most once per minute, including after its callback."""
    target = safe_inapp_path(redirect) or '/'
    if valid_marker(request.cookies.get(LOGOUT_COOKIE), 'logout', 30 * 86400):
        return _fallback(target)
    if valid_marker(request.cookies.get(ATTEMPT_COOKIE), 'attempt', 60):
        return _fallback(target)
    return _start(request, 'continue', target)


@auth_router.get('/auth/callback')
def auth_callback(request: Request, state: str | None = None, code: str | None = None, error: str | None = None):
    runtime = request.app.state.runtime
    browser = request.cookies.get(BROWSER_COOKIE)
    if not state or not browser or bool(code) == bool(error):
        return _error(request, 400, 'invalid_code_or_state')
    try:
        flow = runtime.session_repository.consume_flow(state, browser)
    except Exception:
        return _error(request, 503, 'auth_unavailable')
    if not flow or flow.mode == 'logout':
        return _error(request, 400, 'invalid_code_or_state')
    if error:
        if flow.mode == 'continue' and error in ('login_required', 'interaction_required', 'consent_required'):
            reason = 'session-expired' if request.cookies.get(SESSION_COOKIE_NAME) else 'login'
            return _fallback(flow.redirect, reason)
        return _error(request, 503 if error in ('temporarily_unavailable', 'server_error') else 400, 'auth_unavailable' if error in ('temporarily_unavailable', 'server_error') else 'authentication_failed')
    if not code:
        return _error(request, 400, 'invalid_code_or_state')
    try:
        tokens = runtime.oidc_client.exchange_code_for_tokens(code=code, code_verifier=flow.code_verifier)
        values = session_values(tokens, runtime.oidc_config, nonce=flow.nonce)
        session = runtime.session_repository.complete_flow(state, browser, values, request.cookies.get(SESSION_COOKIE_NAME))
        if session is None:
            return _error(request, 400, 'invalid_code_or_state')
    except SessionInvalid:
        return _error(request, 400, 'invalid_token')
    except Exception:
        return _error(request, 503, 'auth_unavailable')
    response = _redirect(flow.redirect or '/')
    cookie(response, SESSION_COOKIE_NAME, session.session_id)
    # Keep the attempt marker: a successful callback must not permit a loop.
    return response


@auth_router.get('/auth/logout')
def auth_logout_confirmation():
    """Compatibility entry; Caddy serves the actual Svelte confirmation page."""
    return HTMLResponse('<html lang="de"><title>Abmelden</title><h1>Von GUSTAV abmelden?</h1><form method="post" action="/auth/logout"><button>Abmelden</button></form></html>', headers={**HEADERS, "Referrer-Policy": "same-origin"})


@auth_router.post('/auth/logout')
def auth_logout(request: Request):
    """Revoke locally before beginning state-bound IdP logout; never refresh."""
    runtime = request.app.state.runtime
    if not cookie_origin_allowed(request, runtime.oidc_config.redirect_uri):
        return _error(request, 403, 'csrf_forbidden')
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        session = runtime.session_repository.get(sid) if sid else None
        runtime.session_repository.revoke_browser(sid, request.cookies.get(BROWSER_COOKIE))
    except Exception:
        return _error(request, 503, 'auth_unavailable')
    browser = request.cookies.get(BROWSER_COOKIE) or secrets.token_urlsafe(32)
    try:
        flow = runtime.session_repository.create_flow(browser=browser, mode='logout', redirect=None, code_verifier='', nonce='')
        cfg = runtime.oidc_config
        app = urlsplit(cfg.redirect_uri)
        params = {'post_logout_redirect_uri': f'{app.scheme}://{app.netloc}/auth/logout/callback', 'state': flow.state, 'client_id': cfg.client_id}
        if session and session.id_token:
            runtime.oidc_client.end_session(id_token=session.id_token, callback=params['post_logout_redirect_uri'], state=flow.state)
        response = _redirect(f'{cfg.public_base_url or cfg.base_url}/realms/{cfg.realm}/protocol/openid-connect/logout?' + urlencode(params))
        cookie(response, BROWSER_COOKIE, browser, 900)
    except Exception:
        response = _error(request, 503, 'local_logout_only')
    cookie(response, SESSION_COOKIE_NAME, '', 0)
    cookie(response, LOGOUT_COOKIE, marker('logout'), 30 * 86400)
    return response


@auth_router.get('/auth/logout/callback')
def auth_logout_callback(request: Request, state: str | None = None, error: str | None = None):
    try:
        flow = request.app.state.runtime.session_repository.consume_flow(state or '', request.cookies.get(BROWSER_COOKIE) or '')
    except Exception:
        return _error(request, 503, 'local_logout_only')
    if not flow or flow.mode != 'logout' or error:
        return _error(request, 400, 'logout_not_confirmed')
    return _redirect('/auth/logout/success')
