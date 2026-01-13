"""
Contract test: H5P service container should drop root privileges.

Why:
    The H5P sidecar processes uploaded ZIP packages (trusted content model) and
    serves a lot of third-party JavaScript. Running it as root increases the
    blast radius of any vulnerability.

    We accept a pragmatic approach:
    - Container may start as root to ensure the bind-mounted storage is writable.
    - It must then exec the Node process as the non-root `node` user.

Note:
    This is a source-level contract guard. It does not build the image.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_dockerfile_installs_su_exec_and_uses_entrypoint() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dockerfile = repo_root / "h5p-service" / "Dockerfile"
    assert dockerfile.is_file(), f"Missing Dockerfile: {dockerfile}"
    src = dockerfile.read_text(encoding="utf-8")

    assert "su-exec" in src, "Expected su-exec (or similar) to drop privileges"
    assert "entrypoint.sh" in src, "Expected an entrypoint script"
    assert "ENTRYPOINT" in src, "Expected Dockerfile to define ENTRYPOINT"


def test_h5p_entrypoint_execs_node_as_non_root() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    entrypoint = repo_root / "h5p-service" / "entrypoint.sh"
    assert entrypoint.is_file(), f"Missing entrypoint: {entrypoint}"
    src = entrypoint.read_text(encoding="utf-8")

    assert "su-exec" in src
    assert "node:node" in src

