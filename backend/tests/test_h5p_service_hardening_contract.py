"""
Contract tests: H5P service hardening (export header, log hygiene, pagination).

Why:
    The H5P sidecar is a browser-facing service (cookie-auth, same-origin).
    We keep a few security invariants as *source-level* contract guards:
    - Export must not interpolate untrusted values into Content-Disposition.
    - finishedData forwarding must not log upstream response bodies.
    - Student visibility checks must not be hard-capped at a single page (avoid false-deny).

Note:
    These tests do not execute Node; they only validate the service source.
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    if not end_token:
        return src[start:]
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_export_content_disposition_is_sanitized() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    # Guard against regressions like: `filename=${contentId}.h5p` (header injection / invalid chars).
    assert "filename=${contentId}.h5p" not in js

    # We expect a dedicated sanitizer helper.
    assert "sanitizeHeaderFilename" in js

    # And we expect the Content-Disposition filename to be quoted.
    assert 'res.setHeader("Content-Disposition", `attachment; filename="' in js


def test_h5p_finisheddata_does_not_read_or_log_upstream_response_body() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    # Regression guard: do not read/log the response body from the Learning API.
    assert "await r.text(" not in js


def test_h5p_student_visibility_check_uses_access_check_endpoint() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    auth_forwarding_path = repo_root / "h5p-service" / "lib" / "auth_forwarding.mjs"
    assert auth_forwarding_path.is_file(), f"Missing H5P auth forwarding helper: {auth_forwarding_path}"
    js = auth_forwarding_path.read_text(encoding="utf-8")

    block = _extract_block(
        js,
        start_token="export async function checkLearningH5PContentAccess(",
        end_token="",
    )

    # Data minimization: avoid enumerating released sections/tasks for students.
    assert "include=tasks" not in block
    assert "/api/learning/courses/${encodeURIComponent(courseId)}" in block
    assert "/h5p/contents/${encodeURIComponent(contentId)}/access" in block


def test_h5p_upload_default_max_bytes_is_reduced() -> None:
    """Default upload limit should be conservative unless configured explicitly."""

    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    # Regression guard: avoid a huge default (512 MiB).
    assert "512 * 1024 * 1024" not in js
    assert "100 * 1024 * 1024" in js


def test_h5p_internal_teacher_auth_is_secret_bound_and_skips_browser_csrf() -> None:
    """CLI package workflows reach H5P through FastAPI, not browser cookies."""

    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    helper_path = repo_root / "h5p-service" / "lib" / "internal_auth.mjs"
    guards_path = repo_root / "h5p-service" / "lib" / "runtime_guards.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    assert helper_path.is_file(), f"Missing H5P internal auth helper: {helper_path}"
    assert guards_path.is_file(), f"Missing H5P runtime guards helper: {guards_path}"
    js = server_path.read_text(encoding="utf-8")
    helper_js = helper_path.read_text(encoding="utf-8")
    guards_js = guards_path.read_text(encoding="utf-8")

    assert "h5pInternalSharedSecret" in js
    assert "h5pInternalSharedSecret" in js
    assert "authenticateInternalTeacher(req, h5pInternalSharedSecret)" in guards_js
    assert "x-gustav-h5p-internal-secret" in helper_js
    assert "x-gustav-user-sub" in helper_js
    assert "x-gustav-user-roles" in helper_js
    assert "req.gustavInternalAuth = true" in helper_js

    same_origin = _extract_block(
        guards_js,
        start_token="export function requireSameOrigin(req, res, next) {",
        end_token="export function createRequireAuth(",
    )
    assert "isInternalAuth(req)" in same_origin
