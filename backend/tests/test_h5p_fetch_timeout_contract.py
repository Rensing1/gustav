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
    if not end_token:
        return src[start:]
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_service_upstream_fetches_use_fetch_with_timeout() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    auth_forwarding_path = repo_root / "h5p-service" / "lib" / "auth_forwarding.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    assert auth_forwarding_path.is_file(), f"Missing H5P auth forwarding helper: {auth_forwarding_path}"

    js = server_path.read_text(encoding="utf-8")
    auth_forwarding_js = auth_forwarding_path.read_text(encoding="utf-8")

    # fetchGustavMe: should not use unbounded `fetch(...)`.
    me_block = _extract_block(
        auth_forwarding_js,
        start_token="export async function fetchGustavMe(cookieHeader",
        end_token="export async function checkLearningH5PContentAccess",
    )
    assert "fetchWithTimeoutImpl" in me_block
    assert "await fetch(" not in me_block

    # Access-check: same.
    access_block = _extract_block(
        auth_forwarding_js,
        start_token="export async function checkLearningH5PContentAccess(",
        end_token="",
    )
    assert "fetchWithTimeoutImpl" in access_block
    assert "await fetch(" not in access_block

    # finishedData → Learning submission: same.
    finished_block = _extract_block(
        js,
        start_token='app.post("/finishedData"',
        end_token="const ajaxRouter",
    )
    # `finishedData` forwards progress to the Learning API via a helper that is
    # required to use `fetchWithTimeout` internally. We accept either direct
    # usage in the route or usage via the forwarding helper.
    assert ("fetchWithTimeout" in finished_block) or ("forwardLearningSubmission" in finished_block)
    assert "await fetch(" not in finished_block

    forwarding_path = repo_root / "h5p-service" / "lib" / "finished_forwarding.mjs"
    assert forwarding_path.is_file(), f"Missing H5P forwarding helper: {forwarding_path}"
    forwarding_js = forwarding_path.read_text(encoding="utf-8")
    assert "fetchWithTimeout" in forwarding_js
    assert "await fetch(" not in forwarding_js
