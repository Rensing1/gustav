"""
Contract test: H5P service cookie parsing must be robust (no crash on bad encoding).

Why:
    The H5P sidecar reads the `gustav_session` cookie from the Cookie header.
    A malformed percent-encoding (e.g. `%ZZ`) can make `decodeURIComponent`
    throw, which would crash the request handler and turn into a 500.

    We keep this as a source-level contract guard (no Node runtime needed).
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_cookie_parser_wraps_decodeuricomponent_in_try_catch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    block = _extract_block(js, start_token="function parseCookies(", end_token="function parseMaxEntries(")

    # Contract: `decodeURIComponent` may be used, but must not be called unguarded.
    assert "decodeURIComponent" in block
    assert "try" in block and "catch" in block
    assert "out[rawKey] = decodeURIComponent" not in block

