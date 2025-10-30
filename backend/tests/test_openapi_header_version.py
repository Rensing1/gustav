"""
OpenAPI header presence and basic version format.

Why:
- Guard against accidental removal of the required `openapi` top-level field.
- Keep the spec parseable by generators and validators.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_has_required_top_level_header():
    spec = _load_spec()
    assert "openapi" in spec, "OpenAPI spec must include top-level 'openapi' key"
    assert str(spec["openapi"]).startswith("3.0."), "OpenAPI version should be 3.0.x"

