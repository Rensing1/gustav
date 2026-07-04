from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docker_image_packages_deterministic_evidence_modules() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY backend ./backend" in dockerfile
    assert "COPY backend/scratch ./backend/scratch" not in dockerfile
    assert "COPY backend/makecode ./backend/makecode" not in dockerfile
    assert "COPY backend/filius ./backend/filius" not in dockerfile


def test_compose_mounts_backend_package_once_for_local_worker() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count("./backend:/app/backend:z") == 2
    for subpackage in ("learning", "vision", "storage", "scratch", "makecode", "filius"):
        assert f"./backend/{subpackage}:/app/backend/{subpackage}:z" not in compose
    assert "./backend/__init__.py:/app/backend/__init__.py:z" not in compose
