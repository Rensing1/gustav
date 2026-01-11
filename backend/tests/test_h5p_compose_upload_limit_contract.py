"""
Contract test: H5P service must set an explicit upload size limit in docker-compose.

Why:
    The H5P sidecar accepts `.h5p` ZIP uploads (trusted content model). A too
    large default increases the disk DoS surface. We require an explicit
    `H5P_MAX_UPLOAD_BYTES` in `docker-compose.yml` to keep local = prod behavior.
"""

from __future__ import annotations

from pathlib import Path


def test_compose_sets_h5p_max_upload_bytes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / "docker-compose.yml"
    assert compose_path.is_file(), f"Missing compose file: {compose_path}"

    src = compose_path.read_text(encoding="utf-8")
    assert "H5P_MAX_UPLOAD_BYTES" in src

