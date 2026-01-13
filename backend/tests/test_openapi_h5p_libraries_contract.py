"""
OpenAPI contract tests for H5P library provisioning endpoints.

Why:
    Real-world `.h5p` packages can be "content-only" (no `libraries/*`), e.g.
    when downloaded from the H5P Hub. In that case, teachers must be able to
    install the required content-type libraries on the H5P service first.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_h5p_libraries_endpoints_exist_in_openapi():
    spec = _load_spec()
    paths = spec.get("paths") or {}

    assert "/h5p/libraries" in paths, "missing /h5p/libraries in openapi.yml"
    assert "/h5p/libraries/import" in paths, "missing /h5p/libraries/import in openapi.yml"


def test_h5p_libraries_get_contract():
    spec = _load_spec()
    get_op = spec["paths"]["/h5p/libraries"]["get"]

    assert "H5PLibrariesResponse" in (spec.get("components") or {}).get("schemas", {})
    assert get_op.get("security"), "GET /h5p/libraries must require authentication"
    assert "200" in (get_op.get("responses") or {}), "GET /h5p/libraries must define 200 response"


def test_h5p_libraries_import_contract():
    spec = _load_spec()
    post_op = spec["paths"]["/h5p/libraries/import"]["post"]

    assert "H5PLibraryImportResponse" in (spec.get("components") or {}).get("schemas", {})
    assert post_op.get("security"), "POST /h5p/libraries/import must require authentication"

    rb = post_op.get("requestBody") or {}
    assert rb.get("required") is True
    content = rb.get("content") or {}
    assert "multipart/form-data" in content
    schema = (content["multipart/form-data"].get("schema") or {})
    assert "file" in (schema.get("required") or []), "library import must require multipart field 'file'"

    assert "200" in (post_op.get("responses") or {}), "POST /h5p/libraries/import must define 200 response"
