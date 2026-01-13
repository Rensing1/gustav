"""
Contract test: docker-compose should healthcheck the H5P sidecar.

Why:
    The H5P service is a dependency for H5P playback/import/export. A Compose
    healthcheck speeds up local diagnosis and improves restart semantics when
    the sidecar cannot start (e.g., storage not writable).
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_compose_h5p_has_healthcheck() -> None:
    compose_path = Path("docker-compose.yml")
    assert compose_path.is_file(), "docker-compose.yml must exist"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose.get("services", {})
    assert "h5p" in services, "compose must define an h5p service"

    h5p = services["h5p"]
    healthcheck = h5p.get("healthcheck")
    assert healthcheck, "h5p service should define a healthcheck"

    test_cmd = healthcheck.get("test", [])
    assert any("healthz" in str(part) for part in test_cmd), "healthcheck must probe /healthz"

