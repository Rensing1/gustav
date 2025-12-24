"""
E2E: Ensure H5P core + library assets are reachable through `/h5p/*`.

Why:
    The Phase-1 tests prove create/save/load via Import→Player→Export→Re-import.
    For real browser UX we additionally need to ensure that the player HTML
    references same-origin assets and that these assets are actually served
    (core JS/CSS + content type libraries).

How:
    - Login via real OIDC (Keycloak) to obtain `gustav_session`.
    - Import a deterministic `.h5p` fixture to create a content id.
    - Load the player HTML and parse `/h5p/core/*` + `/h5p/libraries/*` asset URLs.
    - Fetch a small sample of those assets and expect `200` + non-empty payload.
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


def _extract_asset_urls(html: str) -> list[str]:
    """Extract src/href URLs from a HTML document."""
    raw = set(re.findall(r"(?:src|href)=(?:\"|')([^\"']+)(?:\"|')", html, re.I))

    urls: set[str] = set()
    for u in raw:
        if not u:
            continue
        if u.startswith("https://") or u.startswith("http://"):
            parsed = urlparse(u)
            if parsed.hostname and parsed.hostname.lower() == "app.localhost":
                urls.add(parsed.path + (f"?{parsed.query}" if parsed.query else ""))
            continue
        urls.add(u)
    return sorted(urls)


def _pick_sample(urls: list[str], *, prefix: str, limit: int) -> list[str]:
    """Pick a stable sample of static assets under a URL prefix."""
    picked: list[str] = []
    for u in urls:
        if not u.startswith(prefix):
            continue
        if not re.search(r"\.(?:js|css|json|png|jpg|jpeg|gif|svg|woff2?|ttf|eot)(?:\?|$)", u, re.I):
            continue
        picked.append(u)
        if len(picked) >= limit:
            break
    return picked


def test_h5p_player_serves_core_and_library_assets():
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    token = _kc_admin_token()

    teacher_email = f"e2e_teacher_assets_{int(time.time())}@example.com"
    teacher_pw = "Passw0rd!e2e"
    teacher_id = _kc_create_user(token, teacher_email, teacher_pw)
    _kc_add_realm_role(token, teacher_id, "teacher")

    student_email = f"e2e_student_assets_{int(time.time())}@example.com"
    student_pw = "Passw0rd!e2e"
    _kc_create_user(token, student_email, student_pw)

    teacher_sess = requests.Session()
    _login_via_oidc(teacher_sess, email=teacher_email, password=teacher_pw)
    student_sess = requests.Session()
    _login_via_oidc(student_sess, email=student_email, password=student_pw)

    fixture_bytes = _build_fixture_h5p_bytes()

    import_headers = {"Origin": WEB_BASE, "Referer": f"{WEB_BASE}/h5p/editor"}
    r_import = teacher_sess.post(
        f"{WEB_BASE}/h5p/contents/import",
        files={"file": ("minimal.h5p", fixture_bytes, "application/zip")},
        headers=import_headers,
        timeout=60,
    )
    assert r_import.status_code in (200, 201), f"Import failed: {r_import.status_code} {r_import.text}"
    content_id = r_import.json().get("content_id")
    assert isinstance(content_id, str) and content_id

    r_player = student_sess.get(
        f"{WEB_BASE}/h5p/player",
        params={"content_id": content_id},
        timeout=30,
    )
    assert r_player.status_code == 200
    assert "text/html" in (r_player.headers.get("content-type") or "")
    _assert_no_external_http_urls(r_player.text)

    urls = _extract_asset_urls(r_player.text)
    core_assets = _pick_sample(urls, prefix="/h5p/core/", limit=3)
    lib_assets = _pick_sample(urls, prefix="/h5p/libraries/", limit=3)
    assert core_assets, "Player HTML must reference /h5p/core/* assets"
    assert lib_assets, "Player HTML must reference /h5p/libraries/* assets"

    for asset_url in core_assets + lib_assets:
        r = student_sess.get(urljoin(f"{WEB_BASE}/", asset_url.lstrip("/")), timeout=20)
        assert r.status_code == 200, f"Asset fetch failed {asset_url}: {r.status_code}"
        assert r.content, f"Asset must not be empty: {asset_url}"


def test_h5p_editor_model_serves_editor_core_assets():
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    token = _kc_admin_token()

    teacher_email = f"e2e_teacher_editor_assets_{int(time.time())}@example.com"
    teacher_pw = "Passw0rd!e2e"
    teacher_id = _kc_create_user(token, teacher_email, teacher_pw)
    _kc_add_realm_role(token, teacher_id, "teacher")

    teacher_sess = requests.Session()
    _login_via_oidc(teacher_sess, email=teacher_email, password=teacher_pw)

    r_model = teacher_sess.get(f"{WEB_BASE}/h5p/editor/model", timeout=30)
    assert r_model.status_code == 200, f"Editor model failed: {r_model.status_code} {r_model.text}"
    model = r_model.json()

    scripts = model.get("scripts") or []
    styles = model.get("styles") or []
    assert isinstance(scripts, list) and scripts
    assert isinstance(styles, list) and styles

    urls = [u for u in scripts + styles if isinstance(u, str)]
    core_assets = _pick_sample(urls, prefix="/h5p/core/", limit=3)
    editor_assets = _pick_sample(urls, prefix="/h5p/editor-assets/", limit=3)

    assert core_assets, "Editor model must reference /h5p/core/* assets"
    assert editor_assets, "Editor model must reference /h5p/editor-assets/* assets"

    for asset_url in core_assets + editor_assets:
        r = teacher_sess.get(urljoin(f"{WEB_BASE}/", asset_url.lstrip("/")), timeout=20)
        assert r.status_code == 200, f"Asset fetch failed {asset_url}: {r.status_code}"
        assert r.content, f"Asset must not be empty: {asset_url}"


def test_h5p_editor_webcomponents_modules_are_resolvable():
    """
    Regression: The Phase-1 editor page uses ES module webcomponents.

    Browser ESM has two pitfalls we want to guard against:
    1) Extensionless relative imports (e.g. `./h5p-editor`) must still resolve.
    2) Bare specifiers (e.g. `deepmerge`, `await-lock`) require an import map.

    If either breaks, the inline module script fails early and the UI buttons
    appear "dead" because event listeners are never attached.
    """
    _wait_for(f"{KC_BASE}/realms/{REALM}/.well-known/openid-configuration")
    _wait_for(f"{WEB_BASE}/health")
    _wait_for(f"{WEB_BASE}/h5p/healthz")

    token = _kc_admin_token()

    teacher_email = f"e2e_teacher_webcomponents_{int(time.time())}@example.com"
    teacher_pw = "Passw0rd!e2e"
    teacher_id = _kc_create_user(token, teacher_email, teacher_pw)
    _kc_add_realm_role(token, teacher_id, "teacher")

    teacher_sess = requests.Session()
    _login_via_oidc(teacher_sess, email=teacher_email, password=teacher_pw)

    r_editor = teacher_sess.get(f"{WEB_BASE}/h5p/editor", timeout=30)
    assert r_editor.status_code == 200
    assert "h5p-editor" in r_editor.text

    assert (
        "Waiting for editor JS" in r_editor.text
    ), "Editor page should show a visible placeholder when JS fails to load"

    assert (
        "__gustav_h5p_editor_init_ok" in r_editor.text
    ), "Editor page should expose an init flag so we can detect partial JS failures"

    # The editor page inlines JS. We rely on line breaks because the script
    # contains `//` comments (without newlines they'd comment out the rest).
    assert "\n" in r_editor.text
    assert "\n    // Workaround:" in r_editor.text

    assert 'type="importmap"' in r_editor.text, "Editor must ship an import map for bare imports"
    assert "deepmerge" in r_editor.text
    assert "await-lock" in r_editor.text
    assert (
        "editor.contentId = undefined;" in r_editor.text
    ), "Editor must force a reload when switching from 'new' to an existing content id"

    r_utils = teacher_sess.get(f"{WEB_BASE}/h5p/webcomponents/h5p-utils.js", timeout=20)
    assert r_utils.status_code == 200
    assert "from './vendor/deepmerge.js'" in r_utils.text
    assert "from 'deepmerge'" not in r_utils.text

    r_dom = teacher_sess.get(f"{WEB_BASE}/h5p/webcomponents/dom-utils.js", timeout=20)
    assert r_dom.status_code == 200
    assert "from './vendor/await-lock.js'" in r_dom.text
    assert "from 'await-lock'" not in r_dom.text

    # Requests as the browser would do when evaluating the module graph.
    paths = [
        "/h5p/webcomponents/index.js",
        "/h5p/webcomponents/h5p-editor",
        "/h5p/webcomponents/h5p-utils",
        "/h5p/webcomponents/dom-utils",
        "/h5p/webcomponents/vendor/deepmerge.js",
        "/h5p/webcomponents/vendor/await-lock.js",
    ]
    for p in paths:
        r = teacher_sess.get(f"{WEB_BASE}{p}", timeout=20)
        assert r.status_code == 200, f"Webcomponent asset must be served: {p} -> {r.status_code}"
        assert r.content, f"Webcomponent asset must not be empty: {p}"
        assert "javascript" in (r.headers.get("content-type") or "").lower(), (
            "Webcomponent modules must be served with a JS MIME type so browsers execute them. "
            f"{p} -> {r.headers.get('content-type')}"
        )
