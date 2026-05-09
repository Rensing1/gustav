from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docker_image_packages_deterministic_evidence_modules() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY backend/scratch ./backend/scratch" in dockerfile
    assert "COPY backend/makecode ./backend/makecode" in dockerfile
    assert "COPY backend/filius ./backend/filius" in dockerfile


def test_compose_mounts_filius_evidence_module_for_local_worker() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./backend/filius:/app/backend/filius:z" in compose
