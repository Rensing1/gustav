"""
Contract test: `/h5p/auth/me` must not report upstream failures as authentication errors.

Why:
    The H5P sidecar forwards the `gustav_session` cookie to the web service's
    `GET /api/me`. If the upstream is unavailable (network errors, 5xx, etc.),
    the sidecar must respond with a 502-class error signal that is semantically
    different from "unauthenticated".

Note:
    Source-level guard: does not execute Node.
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_auth_me_upstream_unavailable_has_distinct_error() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    guards_path = repo_root / "h5p-service" / "lib" / "runtime_guards.mjs"
    assert guards_path.is_file(), f"Missing H5P runtime guards helper: {guards_path}"

    js = guards_path.read_text(encoding="utf-8")
    block = _extract_block(js, start_token="if (!me.ok)", end_token="req.gustavMe = me.payload;")

    assert 'error: "unauthenticated"' in block
    assert 'error: "upstream_unavailable"' in block
    assert '502, { error: "unauthenticated" }' not in block
