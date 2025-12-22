"""
E2E: Verify `/h5p/*` reverse proxy + cookie-based auth handshake.

Why:
    The H5P service must run as a separate process, but still rely on the
    existing GUSTAV session cookie (`gustav_session`). This test ensures:
      - `/h5p/healthz` is reachable through Caddy.
      - `/h5p/auth/me` returns 401 when unauthenticated.
      - After a real OIDC login, `/h5p/auth/me` returns the same principal data
        as `GET /api/me` (validated via cookie forwarding).

How to run locally:
    1) Start services: `docker compose up -d --build caddy web keycloak h5p`
    2) Run: `.venv/bin/pytest -q -m e2e backend/tests_e2e/test_h5p_service_auth_e2e.py`
"""

from __future__ import annotations

import os
import re
import time
from urllib.parse import urljoin

import pytest
import requests


pytestmark = pytest.mark.e2e

WEB_BASE = os.getenv("WEB_BASE", "https://app.localhost")
KC_BASE = os.getenv("KC_BASE", "https://id.localhost")
REALM = os.getenv("KC_REALM", "gustav")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")


def _wait_for(url: str, *, expected=200, timeout_s: int = 60) -> None:
    """Poll a URL until it responds with the expected status or fail fast."""
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == expected or (
                isinstance(expected, (tuple, list)) and r.status_code in expected
            ):
                return
        except requests.RequestException as exc:
            last_err = exc
        time.sleep(1)
    pytest.fail(f"E2E dependency not ready in {timeout_s}s: GET {url} (expected {expected}), last_err={last_err}")


def _kc_admin_token() -> str:
    url = f"{KC_BASE}/realms/master/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
    }
    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def _kc_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _kc_find_user(token: str, email: str) -> str | None:
    url = f"{KC_BASE}/admin/realms/{REALM}/users?email={email}&exact=true"
    r = requests.get(url, headers=_kc_headers(token), timeout=10)
    r.raise_for_status()
    arr = r.json()
    if isinstance(arr, list) and arr:
        return arr[0].get("id")
    return None


def _kc_create_user(token: str, email: str, password: str) -> str:
    """Create or find a user and set a non-temporary password (returns user id)."""
    user_id = _kc_find_user(token, email)
    if not user_id:
        url = f"{KC_BASE}/admin/realms/{REALM}/users"
        payload = {
            "username": email,
            "email": email,
            "firstName": "E2E",
            "lastName": "User",
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
        }
        r = requests.post(url, headers=_kc_headers(token), json=payload, timeout=10)
        if r.status_code not in (201, 409):
            r.raise_for_status()
        user_id = _kc_find_user(token, email)
        assert user_id, "User creation failed: no id returned"

    pw_url = f"{KC_BASE}/admin/realms/{REALM}/users/{user_id}/reset-password"
    pw_payload = {"type": "password", "value": password, "temporary": False}
    r = requests.put(pw_url, headers=_kc_headers(token), json=pw_payload, timeout=10)
    assert r.status_code in (204, 200), f"Failed to set password: {r.status_code} {r.text}"
    return user_id


def _parse_login_form(html: str, base_url: str) -> tuple[str, dict]:
    form_match = re.search(
        r"<form[^>]*id=\"kc-form-login\"[^>]*action=\"([^\"]+)\"[^>]*>(.*?)</form>",
        html,
        re.I | re.S,
    )
    if not form_match:
        raise AssertionError("Keycloak login form not found (kc-form-login)")
    action = form_match.group(1)
    inner = form_match.group(2)
    inputs = dict(re.findall(r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"", inner, re.I))
    action_url = urljoin(base_url, action)
    return action_url, inputs


def _login_via_oidc(sess: requests.Session, *, email: str, password: str) -> None:
    """Perform a full browser login flow and leave the session authenticated."""
    r = sess.get(f"{WEB_BASE}/auth/login", allow_redirects=True, timeout=20)
    assert r.status_code == 200
    assert "kc-form-login" in r.text

    action_url, fields = _parse_login_form(r.text, r.url)
    fields.update({"username": email, "password": password})
    r2 = sess.post(action_url, data=fields, allow_redirects=False, timeout=20)
    assert r2.status_code in (302, 303)

    resp = r2
    for _ in range(15):
        loc = resp.headers.get("Location")
        if not loc:
            break
        next_url = urljoin(resp.url, loc)
        resp = sess.get(next_url, allow_redirects=False, timeout=20)
        if resp.status_code in (200, 204) or not (300 <= resp.status_code < 400):
            break

    assert any(c.name == "gustav_session" for c in sess.cookies), "Session cookie not set"


def test_h5p_healthz_and_auth_me():
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    # Unauthenticated: H5P service must fail-closed
    r0 = requests.get(f"{WEB_BASE}/h5p/auth/me", timeout=10)
    assert r0.status_code == 401

    # Authenticated: cookie must be forwarded to the web service /api/me
    token = _kc_admin_token()
    email = f"e2e_h5p_{int(time.time())}@example.com"
    password = "Passw0rd!e2e"
    _kc_create_user(token, email, password)

    sess = requests.Session()
    _login_via_oidc(sess, email=email, password=password)
    r1 = sess.get(f"{WEB_BASE}/h5p/auth/me", timeout=10)
    assert r1.status_code == 200, f"/h5p/auth/me failed: {r1.status_code} {r1.text}"
    body = r1.json()
    assert body.get("email") == email
    assert isinstance(body.get("roles", []), list)
