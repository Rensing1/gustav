"""
E2E: H5P finishedData ingest must work even when the browser sends `Origin: null`.

Why:
    Some H5P embed modes can end up sending `Origin: null` (e.g., sandboxed iframes).
    We still need to:
      - accept the request when a same-origin Referer is present, and
      - forward the finished score to the Learning API so Teacher dashboards can
        read progress from `learning_submissions(kind='h5p')`.

Regression:
    The H5P service previously rejected `Origin: null` even with a valid Referer,
    and its internal forwarding logic failed to fall back to Referer parsing.
"""

from __future__ import annotations

import os
import re
import time
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import pytest
import requests


pytestmark = pytest.mark.e2e

WEB_BASE = os.getenv("WEB_BASE", "https://app.localhost").rstrip("/")
KC_BASE = os.getenv("KC_BASE", "https://id.localhost").rstrip("/")
REALM = os.getenv("KC_REALM", "gustav")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")


def _wait_for(url: str, *, expected=200, timeout_s: int | None = None) -> None:
    """Poll a URL until it responds with the expected status or fail fast."""
    if timeout_s is None:
        timeout_s = int(os.getenv("E2E_READY_TIMEOUT_S", "60"))
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


def test_h5p_finisheddata_accepts_origin_null_and_persists_learning_submission():
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    token = _kc_admin_token()

    teacher_email = f"e2e_teacher_finisheddata_{int(time.time())}@example.com"
    teacher_pw = "Passw0rd!e2e"
    teacher_id = _kc_create_user(token, teacher_email, teacher_pw)
    _kc_add_realm_role(token, teacher_id, "teacher")

    student_email = f"e2e_student_finisheddata_{int(time.time())}@example.com"
    student_pw = "Passw0rd!e2e"
    student_id = _kc_create_user(token, student_email, student_pw)
    _kc_add_realm_role(token, student_id, "student")

    teacher_sess = requests.Session()
    _login_via_oidc(teacher_sess, email=teacher_email, password=teacher_pw)
    student_sess = requests.Session()
    _login_via_oidc(student_sess, email=student_email, password=student_pw)

    # Import a minimal H5P package to obtain a content_id.
    fixture_bytes = _build_fixture_h5p_bytes()
    r_import = teacher_sess.post(
        f"{WEB_BASE}/h5p/contents/import",
        files={"file": ("minimal.h5p", fixture_bytes, "application/zip")},
        headers={"Origin": WEB_BASE, "Referer": f"{WEB_BASE}/courses"},
        timeout=60,
    )
    assert r_import.status_code in (200, 201), f"Import failed: {r_import.status_code} {r_import.text}"
    content_id = r_import.json().get("content_id")
    assert isinstance(content_id, str) and content_id

    # Create course + unit + released section + H5P task.
    r_course = teacher_sess.post(
        f"{WEB_BASE}/api/teaching/courses",
        json={"title": f"E2E finishedData {int(time.time())}"},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_course.status_code == 201, f"Course create failed: {r_course.status_code} {r_course.text}"
    course_id = r_course.json().get("id")
    assert isinstance(course_id, str) and course_id

    r_unit = teacher_sess.post(
        f"{WEB_BASE}/api/teaching/units",
        json={"title": f"E2E Unit {int(time.time())}"},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_unit.status_code == 201, f"Unit create failed: {r_unit.status_code} {r_unit.text}"
    unit_id = r_unit.json().get("id")
    assert isinstance(unit_id, str) and unit_id

    r_section = teacher_sess.post(
        f"{WEB_BASE}/api/teaching/units/{unit_id}/sections",
        json={"title": "Section A"},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_section.status_code == 201, f"Section create failed: {r_section.status_code} {r_section.text}"
    section_id = r_section.json().get("id")
    assert isinstance(section_id, str) and section_id

    r_task = teacher_sess.post(
        f"{WEB_BASE}/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": "H5P task", "h5p": {"content_id": content_id, "display_options": {}}},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_task.status_code == 201, f"Task create failed: {r_task.status_code} {r_task.text}"
    task_id = r_task.json().get("id")
    assert isinstance(task_id, str) and task_id

    r_mod = teacher_sess.post(
        f"{WEB_BASE}/api/teaching/courses/{course_id}/modules",
        json={"unit_id": unit_id},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_mod.status_code == 201, f"Module create failed: {r_mod.status_code} {r_mod.text}"
    module_id = r_mod.json().get("id")
    assert isinstance(module_id, str) and module_id

    r_release = teacher_sess.patch(
        f"{WEB_BASE}/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
        json={"visible": True},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_release.status_code == 200, f"Release failed: {r_release.status_code} {r_release.text}"

    # Enroll the student into the course.
    r_me = student_sess.get(f"{WEB_BASE}/api/me", timeout=20)
    assert r_me.status_code == 200
    student_sub = r_me.json().get("sub")
    assert isinstance(student_sub, str) and student_sub

    r_add = teacher_sess.post(
        f"{WEB_BASE}/api/teaching/courses/{course_id}/members",
        json={"student_sub": student_sub},
        headers={"Origin": WEB_BASE},
        timeout=20,
    )
    assert r_add.status_code in (201, 204), f"Add member failed: {r_add.status_code} {r_add.text}"

    # Main regression check: finishedData with Origin=null must still persist a submission.
    r_finished = student_sess.post(
        f"{WEB_BASE}/h5p/finishedData",
        params={"course_id": course_id, "task_id": task_id},
        json={"contentId": content_id, "score": 1, "maxScore": 1, "opened": 1, "finished": 2, "time": 3},
        headers={"Origin": "null", "Referer": f"{WEB_BASE}/learning/courses/{course_id}"},
        timeout=30,
    )
    assert r_finished.status_code == 200, f"finishedData failed: {r_finished.status_code} {r_finished.text}"
    assert r_finished.json() == {"success": True}

    r_hist = student_sess.get(
        f"{WEB_BASE}/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
        params={"limit": 5, "offset": 0},
        timeout=20,
    )
    assert r_hist.status_code == 200, f"Submissions list failed: {r_hist.status_code} {r_hist.text}"
    items = r_hist.json()
    assert isinstance(items, list) and items, "Expected at least one saved H5P submission"
    assert any((isinstance(it, dict) and it.get("kind") == "h5p") for it in items)
