"""
Contract test: H5P sidecar must fail fast when storage is not ready.

Why:
    The H5P service relies on a writable storage root for libraries, content
    and uploads. If the storage cannot be initialized at startup, the process
    should exit with a non-zero code so the orchestrator can restart it.

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


def test_h5p_service_exits_on_storage_probe_failure() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    block = _extract_block(
        js,
        start_token="const storage = await probeStorageDirs(storageDirs);",
        end_token="const configPath",
    )
    assert "if (!storage.ok)" in block
    assert "process.exit(1)" in block
