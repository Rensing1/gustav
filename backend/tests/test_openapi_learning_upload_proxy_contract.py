"""
OpenAPI Contract — Learning internal upload proxy (RED).

Ensures the Same-Origin proxy endpoint is documented with security,
query parameters, binary request body, and error responses so FE clients
can rely on the contract.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    spec_path = root / "api" / "openapi.yml"
    return yaml.safe_load(spec_path.read_text(encoding="utf-8"))


def test_openapi_upload_proxy_path_exists():
    spec = _load_spec()
    paths = spec.get("paths", {})
    assert "/api/learning/internal/upload-proxy" in paths, "Missing upload-proxy path in openapi.yml"
    put_op = paths["/api/learning/internal/upload-proxy"].get("put")
    assert put_op is not None, "upload-proxy must define PUT operation"
    assert put_op.get("security") == [{"cookieAuth": []}], "upload-proxy requires cookieAuth"


def test_openapi_upload_proxy_request_body_and_params():
    spec = _load_spec()
    put_op = spec["paths"]["/api/learning/internal/upload-proxy"]["put"]
    params = put_op.get("parameters", [])
    assert any(p.get("name") == "url" and p.get("in") == "query" for p in params), "query parameter `url` missing"
    request_body = put_op.get("requestBody")
    assert request_body and request_body.get("required") is True, "requestBody must be required"
    octet_schema = (
        request_body.get("content", {})
        .get("application/octet-stream", {})
        .get("schema", {})
    )
    assert octet_schema.get("type") == "string" and octet_schema.get("format") == "binary", "body must be binary stream"


def test_openapi_upload_proxy_documents_error_responses():
    spec = _load_spec()
    responses = spec["paths"]["/api/learning/internal/upload-proxy"]["put"]["responses"]
    for status in ("200", "400", "401", "403", "404", "502"):
        assert status in responses, f"upload-proxy must document HTTP {status}"
