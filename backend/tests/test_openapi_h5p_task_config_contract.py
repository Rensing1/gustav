"""
OpenAPI contract test: H5P task config (`H5PTaskConfig`).

Why:
    The platform uses Lumi/H5P content ids that are numeric strings. We enforce
    this consistently across Teaching task configuration and Learning access
    checks to avoid drift and edge cases (e.g., non-ASCII digits).
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_h5p_task_config_content_id_is_numeric_string() -> None:
    spec = _load_spec()
    schema = spec["components"]["schemas"]["H5PTaskConfig"]
    content_id = (schema.get("properties") or {}).get("content_id") or {}
    assert content_id.get("type") == "string"
    assert content_id.get("nullable") is True
    assert content_id.get("pattern") == "^[0-9]+$"

