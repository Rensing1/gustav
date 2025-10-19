"""
E2E: Validate Keycloak registration form errors (HTML Browser Flow).

Covers submitting the IdP registration form with missing/invalid fields and
asserts that an error message is displayed without leaving the registration
page. Runs only when RUN_E2E=1.
"""

from __future__ import annotations

import os
import re
import time
from urllib.parse import urljoin

import pytest
import os
import requests

# Reuse environment for admin access
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")


pytestmark = pytest.mark.e2e

WEB_BASE = os.getenv("WEB_BASE", "http://app.localhost:8100")
KC_BASE = os.getenv("KC_BASE", "http://id.localhost:8100")
REALM = os.getenv("KC_REALM", "gustav")


def _wait_for(url: str, expected: int = 200) -> None:
    last_err = None
    last_status = None
    for _ in range(60):
        try:
            r = requests.get(url, timeout=2)
            last_status = r.status_code
            if r.status_code == expected or (
                isinstance(expected, (tuple, list)) and r.status_code in expected
            ):
                return
        except requests.RequestException as exc:
            last_err = exc
        time.sleep(1)
    pytest.fail(f"E2E dependency not ready: GET {url} expected={expected} last_status={last_status} last_err={last_err}")


def _parse_register_form(html: str, base_url: str) -> tuple[str, dict]:
    m = re.search(
        r"<form[^>]*id=\"kc-register-form\"[^>]*action=\"([^\"]+)\"[^>]*>(.*?)</form>",
        html,
        re.I | re.S,
    )
    if not m:
        raise AssertionError("Keycloak register form not found (kc-register-form)")
    action = urljoin(base_url, m.group(1))
    inner = m.group(2)
    # Collect default inputs (hidden and others with value)
    inputs = dict(re.findall(r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"", inner, re.I))
    return action, inputs


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


def _kc_set_password_policy(policy: str) -> None:
    token = _kc_admin_token()
    # Read realm representation
    r = requests.get(f"{KC_BASE}/admin/realms/{REALM}", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    rep = r.json()
    rep["passwordPolicy"] = policy
    r2 = requests.put(
        f"{KC_BASE}/admin/realms/{REALM}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=rep,
        timeout=10,
    )
    r2.raise_for_status()


def test_register_invalid_shows_error():
    # Ensure password policy is known and relaxed (no special char required)
    _kc_set_password_policy("length(8) and digits(1) and lowerCase(1) and upperCase(1)")
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")

    sess = requests.Session()
    # Go to our login page and follow redirects to IdP
    r = sess.get(f"{WEB_BASE}/auth/register", allow_redirects=True, timeout=20)
    assert r.status_code == 200
    assert "gustav/css/gustav.css" in r.text
    # Either we land directly on the register page or on the login page with a register link.
    if "kc-register-form" not in r.text:
        m = re.search(r"href=\"([^\"]*login-actions/registration[^\"]*)\"", r.text)
        assert m, "Expected a registration link on login page"
        reg_url = urljoin(r.url, m.group(1))
        r = sess.get(reg_url, allow_redirects=True, timeout=20)
        assert r.status_code == 200
        assert "kc-register-form" in r.text

    # Ensure password policy hint is visible on the register page
    assert "Mindestens 8 Zeichen" in r.text or "gustavPasswordPolicyHint" in r.text

    # Submit incomplete data (missing email/password)
    action, fields = _parse_register_form(r.text, r.url)
    fields.update({
        "firstName": "Alice",
        "lastName": "Test",
        # Intentionally omit email/password to trigger validation error
    })
    r2 = sess.post(action, data=fields, allow_redirects=True, timeout=20)
    # Expect to remain on registration page with an error message
    assert r2.status_code == 200
    assert "kc-register-form" in r2.text
    # Keycloak shows an error summary; look for our message container
    assert "kc-message" in r2.text or "alert-error" in r2.text or "pf-m-danger" in r2.text


def test_register_invalid_email_and_weak_password_show_error():
    # Ensure password policy is known and relaxed
    _kc_set_password_policy("length(8) and digits(1) and lowerCase(1) and upperCase(1)")
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")

    sess = requests.Session()
    r = sess.get(f"{WEB_BASE}/auth/register", allow_redirects=True, timeout=20)
    assert r.status_code == 200
    if "kc-register-form" not in r.text:
        m = re.search(r"href=\"([^\"]*login-actions/registration[^\"]*)\"", r.text)
        assert m, "Expected a registration link on login page"
        r = sess.get(urljoin(r.url, m.group(1)), allow_redirects=True, timeout=20)
        assert r.status_code == 200
        assert "kc-register-form" in r.text

    # 1) Invalid email format
    action, fields = _parse_register_form(r.text, r.url)
    fields.update({
        "firstName": "Alice",
        "lastName": "Test",
        "email": "not-an-email",
        "password": "Passw0rd!e2e",  # strong enough
        "password-confirm": "Passw0rd!e2e",
    })
    r_bad_email = sess.post(action, data=fields, allow_redirects=True, timeout=20)
    assert r_bad_email.status_code == 200
    assert "kc-register-form" in r_bad_email.text
    assert "kc-message" in r_bad_email.text or "alert-error" in r_bad_email.text or "pf-m-danger" in r_bad_email.text

    # 2) Weak password (requires password policy in realm)
    action2, fields2 = _parse_register_form(r.text, r.url)
    # If username field is required, provide one to isolate password failure
    if re.search(r'name=\"username\"', r.text):
        fields2["username"] = f"alice_{int(time.time())}"
    fields2.update({
        "firstName": "Alice",
        "lastName": "Test",
        "email": f"alice_{int(os.environ.get('PYTEST_XDIST_WORKER', '0') or 0)}@example.com",
        "password": "abc",
        "password-confirm": "abc",
    })
    r_weak_pw = sess.post(action2, data=fields2, allow_redirects=True, timeout=20)
    assert r_weak_pw.status_code == 200
    assert "kc-register-form" in r_weak_pw.text
    assert "kc-message" in r_weak_pw.text or "alert-error" in r_weak_pw.text or "pf-m-danger" in r_weak_pw.text


def test_register_password_mismatch_and_duplicate_email():
    _kc_set_password_policy("length(8) and digits(1) and lowerCase(1) and upperCase(1)")
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")

    sess = requests.Session()
    r = sess.get(f"{WEB_BASE}/auth/register", allow_redirects=True, timeout=20)
    assert r.status_code == 200
    if "kc-register-form" not in r.text:
        m = re.search(r"href=\"([^\"]*login-actions/registration[^\"]*)\"", r.text)
        assert m
        r = sess.get(urljoin(r.url, m.group(1)), allow_redirects=True, timeout=20)
        assert r.status_code == 200
        assert "kc-register-form" in r.text

    # 1) Password confirmation mismatch
    action, fields = _parse_register_form(r.text, r.url)
    email = f"mismatch_{int(time.time())}@example.com"
    fields.update({
        "firstName": "Bob",
        "lastName": "Mismatch",
        "email": email,
        "password": "StrongPass1",
        "password-confirm": "StrongPass2",
    })
    if re.search(r'name=\"username\"', r.text):
        fields["username"] = f"bob_{int(time.time())}"
    r_mis = sess.post(action, data=fields, allow_redirects=True, timeout=20)
    assert r_mis.status_code == 200 and "kc-register-form" in r_mis.text
    assert "kc-message" in r_mis.text or "alert-error" in r_mis.text or "pf-m-danger" in r_mis.text

    # 2) Duplicate email
    # Create the user via admin API first
    token = _kc_admin_token()
    create_url = f"{KC_BASE}/admin/realms/{REALM}/users"
    payload = {
        "username": email,
        "email": email,
        "enabled": True,
        "emailVerified": True,
    }
    r_create = requests.post(create_url, headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=10)
    # 201 or 409 are both fine for setup
    assert r_create.status_code in (201, 409)

    # Try to register again with same email
    r_dupe = sess.post(action, data=fields | {"password": "StrongPass1", "password-confirm": "StrongPass1"}, allow_redirects=True, timeout=20)
    assert r_dupe.status_code == 200 and "kc-register-form" in r_dupe.text
    assert "kc-message" in r_dupe.text or "alert-error" in r_dupe.text or "pf-m-danger" in r_dupe.text
