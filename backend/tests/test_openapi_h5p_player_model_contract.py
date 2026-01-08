"""
OpenAPI contract tests for the H5P player model endpoint.

Why:
    The student (and teacher preview) UI embeds Lumi's `<h5p-player>` webcomponent.
    This requires a JSON "player model" endpoint that is contract-defined.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_h5p_player_model_endpoint_exists_in_openapi():
    spec = _load_spec()
    paths = spec.get("paths") or {}
    assert "/h5p/player/model" in paths, "missing /h5p/player/model in openapi.yml"


def test_h5p_player_model_contract():
    spec = _load_spec()
    get_op = spec["paths"]["/h5p/player/model"]["get"]
    schemas = (spec.get("components") or {}).get("schemas", {})
    assert "H5PPlayerModelResponse" in schemas
    assert get_op.get("security"), "GET /h5p/player/model must require authentication"
    assert "200" in (get_op.get("responses") or {}), "GET /h5p/player/model must define 200 response"

