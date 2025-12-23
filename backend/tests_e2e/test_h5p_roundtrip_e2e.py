"""
E2E: H5P Phase-1 roundtrip (create/save/load) through the `/h5p/*` service.

Trusted-content model:
    All teachers are trusted. H5P packages/libraries are treated as executable
    code and may only be imported/updated/exported by role `teacher` (or `admin`).

Proof strategy for "save" without browser automation:
    Import (.h5p) → Player load → Export (.h5p) → Re-import → Player load.
"""

from __future__ import annotations

import os
import re
import time
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pytest
import requests


pytestmark = pytest.mark.e2e

WEB_BASE = os.getenv("WEB_BASE", "https://app.localhost").rstrip("/")
KC_BASE = os.getenv("KC_BASE", "https://id.localhost").rstrip("/")
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
    # 204 No Content on success
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


def _build_fixture_h5p_bytes() -> bytes:
    """Build a deterministic `.h5p` ZIP in-memory from repo fixture files."""
    base_dir = Path(__file__).resolve().parent / "fixtures" / "h5p" / "minimal"
    assert base_dir.is_dir(), f"Fixture directory missing: {base_dir}"

    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(base_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(base_dir).as_posix()
            zf.write(p, rel)
    return buf.getvalue()


def _assert_no_external_http_urls(html: str) -> None:
    """Ensure HTML does not reference external http(s) URLs (offline-first)."""
    for m in re.finditer(r"https?://[^\s\"'<>]+", html):
        url = m.group(0)
        host = (urlparse(url).hostname or "").lower()
        assert host == "app.localhost", f"Unexpected external URL in HTML: {url}"


def test_h5p_import_export_roundtrip():
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    token = _kc_admin_token()

    teacher_email = f"e2e_teacher_{int(time.time())}@example.com"
    teacher_pw = "Passw0rd!e2e"
    teacher_id = _kc_create_user(token, teacher_email, teacher_pw)
    _kc_add_realm_role(token, teacher_id, "teacher")

    student_email = f"e2e_student_{int(time.time())}@example.com"
    student_pw = "Passw0rd!e2e"
    _kc_create_user(token, student_email, student_pw)

    teacher_sess = requests.Session()
    _login_via_oidc(teacher_sess, email=teacher_email, password=teacher_pw)
    student_sess = requests.Session()
    _login_via_oidc(student_sess, email=student_email, password=student_pw)

    fixture_bytes = _build_fixture_h5p_bytes()

    # 1) Import (create)
    import_headers = {
        "Origin": WEB_BASE,
        "Referer": f"{WEB_BASE}/h5p/editor",
    }
    r_import = teacher_sess.post(
        f"{WEB_BASE}/h5p/contents/import",
        files={"file": ("minimal.h5p", fixture_bytes, "application/zip")},
        headers=import_headers,
        timeout=60,
    )
    assert r_import.status_code in (200, 201), f"Import failed: {r_import.status_code} {r_import.text}"
    body = r_import.json()
    assert isinstance(body, dict) and isinstance(body.get("content_id"), str) and body["content_id"]
    content_id_1 = body["content_id"]

    # 2) Load (player)
    r_player = student_sess.get(
        f"{WEB_BASE}/h5p/player",
        params={"content_id": content_id_1},
        timeout=30,
    )
    assert r_player.status_code == 200
    assert "text/html" in (r_player.headers.get("content-type") or "")
    _assert_no_external_http_urls(r_player.text)

    # 3) Export (save proof part 1)
    r_export = teacher_sess.get(
        f"{WEB_BASE}/h5p/contents/{content_id_1}/export",
        timeout=60,
    )
    assert r_export.status_code == 200
    assert (r_export.headers.get("content-type") or "").startswith("application/zip")
    assert r_export.content[:2] == b"PK", "Export must be a ZIP (.h5p)"

    # 4) Re-import (save proof part 2)
    r_reimport = teacher_sess.post(
        f"{WEB_BASE}/h5p/contents/import",
        files={"file": ("exported.h5p", r_export.content, "application/zip")},
        headers=import_headers,
        timeout=60,
    )
    assert r_reimport.status_code in (200, 201), f"Re-import failed: {r_reimport.status_code} {r_reimport.text}"
    body2 = r_reimport.json()
    assert isinstance(body2, dict) and isinstance(body2.get("content_id"), str) and body2["content_id"]
    content_id_2 = body2["content_id"]
    assert content_id_2 != content_id_1, "Re-import should create a new content id for deterministic proof"

    # 5) Reload (load proof)
    r_player2 = student_sess.get(
        f"{WEB_BASE}/h5p/player",
        params={"content_id": content_id_2},
        timeout=30,
    )
    assert r_player2.status_code == 200
    _assert_no_external_http_urls(r_player2.text)

