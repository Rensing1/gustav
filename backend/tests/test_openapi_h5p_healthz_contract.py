"""
OpenAPI contract test: `/h5p/healthz` must be minimal and privacy-safe.

Why:
    The H5P sidecar exposes an unauthenticated readiness probe through the
    reverse proxy. The response must remain a minimal public signal (no internal
    filesystem paths, no raw errors), and the OpenAPI contract must match the
    implementation and existing privacy guards.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_h5p_healthz_contract() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}
    assert "/h5p/healthz" in paths, "missing /h5p/healthz in openapi.yml"

    get_op = paths["/h5p/healthz"]["get"]
    assert get_op.get("security") == [], "GET /h5p/healthz must be public (security: [])"

    description = str(get_op.get("description") or "")
    assert "/data/h5p" not in description, "GET /h5p/healthz must not document internal filesystem paths"

    schemas = (spec.get("components") or {}).get("schemas", {})
    assert "H5PHealth" in schemas
    assert "H5PStorageReadiness" in schemas

    storage = schemas["H5PStorageReadiness"]
    required = storage.get("required") or []
    assert required == ["ok"], "H5PStorageReadiness must require only 'ok'"
    assert storage.get("additionalProperties") is False

    props = storage.get("properties") or {}
    assert set(props.keys()) == {"ok"}, "H5PStorageReadiness must expose only the 'ok' flag publicly"

    health = schemas["H5PHealth"]
    storage_ref = ((health.get("properties") or {}).get("storage") or {}).get("$ref")
    assert storage_ref == "#/components/schemas/H5PStorageReadiness"

    responses = get_op.get("responses") or {}
    assert "200" in responses and "503" in responses
    for code in ("200", "503"):
        schema_ref = (
            (((responses[code].get("content") or {}).get("application/json") or {}).get("schema") or {}).get("$ref")
        )
        assert schema_ref == "#/components/schemas/H5PHealth", f"GET /h5p/healthz {code} must return H5PHealth"

