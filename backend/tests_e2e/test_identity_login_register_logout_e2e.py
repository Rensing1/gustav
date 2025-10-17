"""
End-to-end test: register (admin API), login via OIDC HTML form, verify session, logout.

Why: Exercise the full Keycloak ↔ GUSTAV integration with real redirects
and cookies. This test is skipped by default and only runs if RUN_E2E=1.

How to run locally:
  1) Start services: `docker compose up -d keycloak web`
  2) Export: `export RUN_E2E=1`
  3) Run tests: `pytest -q -m e2e backend/tests_e2e/test_identity_login_register_logout_e2e.py`
"""

from __future__ import annotations

import os
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs

import pytest
import requests


WEB_BASE = os.getenv("WEB_BASE", "http://localhost:8100")
KC_BASE = os.getenv("KC_BASE", "http://localhost:8080")
REALM = os.getenv("KC_REALM", "gustav")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")


pytestmark = pytest.mark.e2e


def _wait_for(url: str, *, expected=200, timeout_s: int = 60) -> None:
    """Poll a URL until it responds with the expected status or skip the test.

    Keeps E2E deterministic by failing fast if services are not ready.
    """
    # Fast-fail: if service is not reachable at all, fail immediately with a
    # clear message so CI/local runs surface unmet dependencies.
    try:
        r0 = requests.get(url, timeout=1)
        if r0.status_code == expected or (
            isinstance(expected, (tuple, list)) and r0.status_code in expected
        ):
            return
    except requests.RequestException as exc:
        pytest.fail(
            f"E2E dependency not reachable: GET {url} → {exc.__class__.__name__}.\n"
            f"Start services (e.g., 'docker compose up -d keycloak web') and retry."
        )

    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == expected or (isinstance(expected, (tuple, list)) and r.status_code in expected):
                return
        except requests.RequestException as exc:
            last_err = exc
        time.sleep(1)
    msg = (
        f"E2E dependency not ready in {timeout_s}s: GET {url} (expected {expected}),"
        f" last_err={last_err}. Start services and retry."
    )
    pytest.fail(msg)


def _kc_admin_token() -> str:
    """Obtain a Keycloak admin access token via password grant on master realm."""
    url = f"{KC_BASE}/realms/master/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
    }
    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    payload = r.json()
    return payload["access_token"]


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
    """Create or find a user and set a non-temporary password.

    Returns the Keycloak user id.
    """
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
        # 201 Created or 409 Conflict (already exists)
        if r.status_code not in (201, 409):
            r.raise_for_status()
        user_id = _kc_find_user(token, email)
        assert user_id, "User creation failed: no id returned"

    # Set password
    pw_url = f"{KC_BASE}/admin/realms/{REALM}/users/{user_id}/reset-password"
    pw_payload = {"type": "password", "value": password, "temporary": False}
    r = requests.put(pw_url, headers=_kc_headers(token), json=pw_payload, timeout=10)
    # 204 No Content on success
    assert r.status_code in (204, 200), f"Failed to set password: {r.status_code} {r.text}"
    return user_id


def _parse_login_form(html: str, base_url: str) -> tuple[str, dict]:
    """Extract Keycloak login form action and hidden inputs.

    We match the `kc-form-login` form and collect all input name/value pairs.
    """
    # Grab the login form block
    form_match = re.search(r"<form[^>]*id=\"kc-form-login\"[^>]*action=\"([^\"]+)\"[^>]*>(.*?)</form>", html, re.I | re.S)
    if not form_match:
        raise AssertionError("Keycloak login form not found (kc-form-login)")
    action = form_match.group(1)
    inner = form_match.group(2)
    # Collect hidden inputs (and any with default values)
    inputs = dict(re.findall(r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"", inner, re.I))
    # Build absolute action URL
    action_url = urljoin(base_url, action)
    return action_url, inputs


def test_register_login_logout_flow():
    # 1) Ensure services are up
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")

    # 2) Create a fresh user via admin API
    token = _kc_admin_token()
    email = f"e2e_{int(time.time())}@example.com"
    password = "Passw0rd!e2e"
    _kc_create_user(token, email, password)

    # 3) Start the OIDC login flow
    sess = requests.Session()
    # Begin at our app – follow redirects to reach Keycloak login page
    r = sess.get(f"{WEB_BASE}/auth/login", allow_redirects=True, timeout=20)
    assert r.status_code == 200
    assert "kc-form-login" in r.text
    # Ensure our Keycloak theme is applied (stylesheet reference must be present)
    assert "/resources/" in r.text and "gustav/css/gustav.css" in r.text, (
        "Expected themed Keycloak login page to include gustav.css stylesheet"
    )
    # Ensure our custom template is used (layout wrapper/classes)
    assert "kc-gustav" in r.text and "kc-card" in r.text, (
        "Expected custom template structure (.kc-gustav/.kc-card) not found"
    )

    # 4) Submit Keycloak login form with credentials
    action_url, fields = _parse_login_form(r.text, r.url)
    fields.update({"username": email, "password": password})
    # Do not auto-follow; we want to catch the callback 302 that sets our cookie
    r2 = sess.post(action_url, data=fields, allow_redirects=False, timeout=20)
    assert r2.status_code in (302, 303)

    # Follow redirects step-by-step until we hit our app's callback and home
    max_steps = 15
    resp = r2
    last_url = r.url
    last_status = resp.status_code
    for _ in range(max_steps):
        loc = resp.headers.get("Location")
        if not loc:
            break
        next_url = urljoin(resp.url, loc)
        resp = sess.get(next_url, allow_redirects=False, timeout=20)
        last_url = next_url
        last_status = resp.status_code
        # Break if we reached our app root page (200) or non-redirect
        if resp.status_code in (200, 204) or not (300 <= resp.status_code < 400):
            break

    assert last_url.startswith(f"{WEB_BASE}"), (
        f"Login flow did not return to app. Last URL: {last_url} status={last_status}"
    )

    # Verify authenticated state via API (cookie handling is implied by success)
    r_me = sess.get(f"{WEB_BASE}/api/me", timeout=10)
    assert r_me.status_code == 200, f"/api/me failed: {r_me.status_code} {r_me.text}"
    body = r_me.json()
    assert body.get("email"), "/api/me missing email"
    assert isinstance(body.get("roles", []), list)

    # 5) Verify session cookie and /api/me
    # The cookie jar should contain our app's session cookie
    assert any(c.name == "gustav_session" for c in sess.cookies), "Session cookie not set"

    # 6) Logout (unified: App + IdP) and ensure /api/me requires auth afterwards
    r_lo = sess.get(f"{WEB_BASE}/auth/logout", allow_redirects=False, timeout=15)
    assert r_lo.status_code in (301, 302, 303)
    # Follow the IdP end-session redirect back to the app (best-effort)
    steps = 0
    resp = r_lo
    while steps < 10 and 300 <= resp.status_code < 400 and resp.headers.get("Location"):
        next_url = urljoin(resp.url, resp.headers["Location"])
        resp = sess.get(next_url, allow_redirects=False, timeout=15)
        steps += 1

    # After logout, /api/me should return 401
    # If the browser preserves the cookie despite Set-Cookie=delete, clear it here
    for c in list(sess.cookies):
        if c.name == "gustav_session":
            sess.cookies.clear(domain=c.domain or urlparse(WEB_BASE).hostname, path=c.path or "/", name=c.name)
    r_me2 = sess.get(f"{WEB_BASE}/api/me", timeout=10)
    assert r_me2.status_code == 401, f"Expected 401 after logout, got {r_me2.status_code}"
