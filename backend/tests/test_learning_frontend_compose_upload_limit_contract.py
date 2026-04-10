"""
Contract test: frontend service must accept learner upload forms larger than 512 KiB.

Why:
    The learner task route currently receives file uploads as multipart form
    data in the SvelteKit action before forwarding them to the Learning API.
    adapter-node defaults to `BODY_SIZE_LIMIT=512K`, which causes a generic
    500 before our own 10 MiB upload contract can run. Compose must therefore
    set an explicit frontend body limit above the Learning upload ceiling.
"""

from __future__ import annotations

from pathlib import Path


def test_compose_sets_frontend_body_size_limit_for_learning_uploads() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / "docker-compose.yml"
    assert compose_path.is_file(), f"Missing compose file: {compose_path}"

    src = compose_path.read_text(encoding="utf-8")
    assert "BODY_SIZE_LIMIT=11M" in src
