"""OpenAPI contract tests for bridging Svelte BFF auth to app sessions."""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_app_session_sync_exists_in_openapi() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}

    assert "/api/app/session-sync" in paths, "missing /api/app/session-sync in openapi.yml"


def test_app_session_sync_contract() -> None:
    spec = _load_spec()
    post_op = spec["paths"]["/api/app/session-sync"]["post"]

    assert post_op.get("security"), "POST /api/app/session-sync must require authentication"
    assert post_op.get("security") == [{"bearerAuth": []}]
    request_body = post_op.get("requestBody") or {}
    assert request_body.get("required") is False
    schema = (
        ((request_body.get("content") or {}).get("application/json") or {}).get("schema")
        or {}
    )
    assert schema.get("$ref") == "#/components/schemas/AppSessionSyncRequest"

    responses = post_op.get("responses") or {}
    assert "204" in responses, "POST /api/app/session-sync must define 204 response"
    assert "401" in responses, "POST /api/app/session-sync must define 401 response"

    success_headers = responses["204"].get("headers") or {}
    assert "Set-Cookie" in success_headers, "204 response must document the gustav_session cookie"

    unauthorized = (responses["401"].get("content") or {}).get("application/json", {}).get("schema") or {}
    assert unauthorized.get("$ref") == "#/components/schemas/Error"
