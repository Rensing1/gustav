"""
Contract test: `/h5p/healthz` must not leak filesystem paths or exception details.

Why:
    The H5P sidecar exposes an unauthenticated readiness probe (`GET /healthz`)
    through the reverse proxy. This endpoint must be safe to expose publicly:
    it should provide a minimal signal only and avoid leaking internal paths
    (e.g. storage roots) or error strings.

Note:
    This is a source-level contract guard. It does not execute Node.
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_healthz_response_is_minimal() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    healthz_block = _extract_block(
        js,
        start_token='app.get("/healthz"',
        end_token="app.use(requireAuth);",
    )

    # Contract: do not expose raw probeStorage output (contains root + error).
    assert "storage," not in healthz_block

    # Contract: do not mention root paths or raw error strings in the payload.
    assert "root:" not in healthz_block
    assert '"root"' not in healthz_block
    assert "error:" not in healthz_block
    assert '"error"' not in healthz_block

    # Minimal storage signal is allowed.
    assert "storage.ok" in healthz_block
