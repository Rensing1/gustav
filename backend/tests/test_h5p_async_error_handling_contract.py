"""
Contract test: H5P service must not crash on async route errors (Express 4).

Why:
    Express 4 does not automatically propagate rejected Promises from async
    route handlers into the error middleware. Unhandled rejections can crash
    the process (DoS) when upstream fetches or storage ops fail.

    We keep this as a source-level contract guard (no Node runtime needed).
"""

from __future__ import annotations

from pathlib import Path


def _assert_async_handler_used(js: str, token: str) -> None:
    idx = js.find(token)
    assert idx != -1, f"Missing route token: {token}"
    window = js[idx : idx + 1200]
    assert "asyncHandler" in window, f"Route must be wrapped via asyncHandler: {token}"


def test_h5p_service_wraps_async_routes_and_has_error_middleware() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    # Contract: define a wrapper for async route handlers and use it consistently.
    assert "function asyncHandler" in js or "const asyncHandler" in js

    for token in (
        'app.get("/healthz"',
        'app.get("/editor/model"',
        'app.get("/player/model"',
        'app.get("/player/review"',
        'app.post("/contents"',
        'app.patch("/contents/:contentId"',
        'app.get("/libraries"',
        '"/libraries/import"',
        '"/contents/import"',
        'app.get("/player"',
        'app.get("/contents/:contentId/export"',
        'app.post("/ajax"',
        'app.post("/finishedData"',
    ):
        _assert_async_handler_used(js, token)

    # Contract: a central error middleware exists for unhandled exceptions.
    assert "app.use((err, req, res" in js or "app.use(function (err, req, res" in js

