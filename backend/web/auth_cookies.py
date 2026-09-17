"""Opaque flow binding and signed continuation/suppression cookies."""
import hashlib
import hmac
import os
import time

BROWSER_COOKIE = 'gustav_auth_browser'
ATTEMPT_COOKIE = 'gustav_auth_attempt'
LOGOUT_COOKIE = 'gustav_auth_logged_out'


def cookie(response, name, value, max_age=None):
    response.set_cookie(name, value, path='/', secure=True, httponly=True, samesite='lax', max_age=max_age)


def marker(kind: str) -> str:
    payload = f'{kind}:{int(time.time())}'
    return f'{payload}:{_sign(payload)}'


def valid_marker(value: str | None, kind: str, lifetime: int) -> bool:
    try:
        payload, signature = (value or '').rsplit(':', 1)
        mode, timestamp = payload.split(':')
        return mode == kind and 0 <= time.time() - int(timestamp) < lifetime and hmac.compare_digest(signature, _sign(payload))
    except (ValueError, TypeError):
        return False


def _sign(payload: str) -> str:
    secret = os.environ.get('APP_CSRF_TOKEN_SECRET', '')
    if len(secret) < 32:
        raise RuntimeError('APP_CSRF_TOKEN_SECRET must contain at least 32 characters')
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
