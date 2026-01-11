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
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    block = _extract_block(
        js,
        start_token="async function checkLearningH5PContentAccess(",
        end_token="async function requireAuth(",
    )

    # Data minimization: avoid enumerating released sections/tasks for students.
    assert "include=tasks" not in block
    assert "/api/learning/courses/${encodeURIComponent(courseId)}/h5p/contents/${encodeURIComponent(contentId)}/access" in block
