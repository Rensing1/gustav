"""
Contract test: H5P sidecar upstream fetches must have hard timeouts.

Why:
    The H5P service calls back into the GUSTAV web/Learning APIs (cookie-auth).
    Unbounded fetches can hang forever on network/proxy issues and tie up the
    process (DoS). We require a central `fetchWithTimeout` helper for upstream
    calls.

Note:
    Source-level guard only (does not execute Node).
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_service_upstream_fetches_use_fetch_with_timeout() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    # fetchGustavMe: should not use unbounded `fetch(...)`.
    me_block = _extract_block(
        js,
        start_token="async function fetchGustavMe(cookieHeader) {",
        end_token="async function checkLearningH5PContentAccess",
    )
    assert "fetchWithTimeout" in me_block
    assert "await fetch(" not in me_block

    # Access-check: same.
    access_block = _extract_block(
        js,
        start_token="async function checkLearningH5PContentAccess(",
        end_token="async function requireAuth",
    )
    assert "fetchWithTimeout" in access_block
    assert "await fetch(" not in access_block

    # finishedData → Learning submission: same.
    finished_block = _extract_block(
        js,
        start_token='app.post("/finishedData"',
        end_token="const ajaxRouter",
    )
    assert "fetchWithTimeout" in finished_block
    assert "await fetch(" not in finished_block

