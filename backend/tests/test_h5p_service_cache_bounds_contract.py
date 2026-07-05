"""
Contract tests: H5P service cache bounds and cache-control invariants.

Why:
    The H5P sidecar is a long-running Node process. Two in-memory maps are used
    as small, short-lived caches (auth lookups and per-content access checks).
    Without explicit bounds, these can grow unbounded over time.

    Additionally, responses are cookie-authenticated and must be non-cacheable
    (`private, no-store`) to avoid storing sensitive data in browser/proxies.
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def _load_h5p_server_source() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    return server_path.read_text(encoding="utf-8")


def test_h5p_sendjson_sets_private_no_store() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    response_helper_path = repo_root / "h5p-service" / "lib" / "response_helpers.mjs"
    assert response_helper_path.is_file(), f"Missing H5P response helper: {response_helper_path}"
    js = response_helper_path.read_text(encoding="utf-8")
    block = _extract_block(js, start_token="export function sendJson(", end_token="export function sendHtml(")
    assert 'res.setHeader("Cache-Control", "private, no-store")' in block


def test_h5p_auth_caches_are_bounded_and_swept() -> None:
    js = _load_h5p_server_source()

    # Contract: explicit max-size knobs exist and are used for pruning.
    assert "AUTH_CACHE_MAX_ENTRIES" in js
    assert "H5P_AUTH_CACHE_MAX_ENTRIES" in js
    assert "function pruneCacheToMaxEntries" in js

    # Both caches must be pruned (TTL sweep + max-size cap).
    assert "pruneCacheToMaxEntries(authCache" in js
    assert "pruneCacheToMaxEntries(h5pContentAccessCache" in js
