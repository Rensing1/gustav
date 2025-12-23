"""
E2E: H5P import error semantics.

Why:
    Real-world `.h5p` packages may be "content-only" exports (no `libraries/*`),
    e.g. when downloaded from the H5P Hub. In an offline-first setup this must
    fail deterministically with a clear error that tells the teacher which
    libraries need to be installed first.

Contract:
    `POST /h5p/contents/import` returns `400` with `{"error": "...", "detail": "..."}`.
"""

from __future__ import annotations

import json
import os
import re
import time
import zipfile
from io import BytesIO
from urllib.parse import urljoin

import pytest
import requests


pytestmark = pytest.mark.e2e

WEB_BASE = os.getenv("WEB_BASE", "https://app.localhost").rstrip("/")
KC_BASE = os.getenv("KC_BASE", "https://id.localhost").rstrip("/")
REALM = os.getenv("KC_REALM", "gustav")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")


def _wait_for(url: str, *, expected=200, timeout_s: int = 60) -> None:
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
    pytest.fail(
        f"E2E dependency not ready in {timeout_s}s: GET {url} (expected {expected}), last_err={last_err}"
    )


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


def _kc_get_role(token: str, role_name: str) -> dict:
    url = f"{KC_BASE}/admin/realms/{REALM}/roles/{role_name}"
    r = requests.get(url, headers=_kc_headers(token), timeout=10)
    r.raise_for_status()
    data = r.json()
    assert isinstance(data, dict) and data.get("name") == role_name
    return data


def _kc_add_realm_role(token: str, user_id: str, role_name: str) -> None:
    role = _kc_get_role(token, role_name)
    url = f"{KC_BASE}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm"
    r = requests.post(url, headers=_kc_headers(token), json=[role], timeout=10)
    assert r.status_code in (204, 200), f"Failed to add role {role_name}: {r.status_code} {r.text}"


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


def _build_content_only_h5p_bytes(*, main_library: str, major: int, minor: int) -> bytes:
    """
    Build a content-only `.h5p` in-memory.

    This mimics Hub exports that include `h5p.json` + `content/content.json`
    but no `libraries/*` directories.
    """
    h5p_json = {
        "title": "Content-only package (E2E)",
        "language": "en",
        "mainLibrary": main_library,
        "embedTypes": ["iframe"],
        "license": "U",
        "preloadedDependencies": [
            {"machineName": main_library, "majorVersion": str(major), "minorVersion": str(minor)}
        ],
    }
    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("h5p.json", json.dumps(h5p_json, separators=(",", ":")))
        zf.writestr("content/content.json", "{}")
    return buf.getvalue()


def test_import_content_only_package_reports_missing_libraries():
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    token = _kc_admin_token()

    teacher_email = f"e2e_teacher_missing_libs_{int(time.time())}@example.com"
    teacher_pw = "Passw0rd!e2e"
    teacher_id = _kc_create_user(token, teacher_email, teacher_pw)
    _kc_add_realm_role(token, teacher_id, "teacher")

    sess = requests.Session()
    _login_via_oidc(sess, email=teacher_email, password=teacher_pw)

    pkg = _build_content_only_h5p_bytes(main_library="H5P.DoesNotExist", major=99, minor=99)
    headers = {"Origin": WEB_BASE, "Referer": f"{WEB_BASE}/h5p/editor"}
    r = sess.post(
        f"{WEB_BASE}/h5p/contents/import",
        files={"file": ("content-only.h5p", pkg, "application/zip")},
        headers=headers,
        timeout=60,
    )
    assert r.status_code == 400
    body = r.json()
    assert body.get("error") == "missing_libraries"
    assert "H5P.DoesNotExist-99.99" in (body.get("detail") or "")
