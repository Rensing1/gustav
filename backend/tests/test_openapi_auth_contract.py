"""
OpenAPI auth & CSRF contract regression tests.

Why:
- CSRF-geschützte Write-Endpunkte sollen `Vary: Origin` deklarieren, damit
  Reverse-Proxies keine Antworten zwischen Origins teilen.
"""
from __future__ import annotations

from pathlib import Path
import re
import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    spec_path = root / "api" / "openapi.yml"
    return yaml.safe_load(spec_path.read_text(encoding="utf-8"))


def _response(spec: dict, path: str, method: str, status: str) -> dict:
    return spec["paths"][path][method]["responses"][status]


def test_csrf_write_endpoints_vary_origin():
    spec = _load_spec()
    path = "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"
    response = _response(spec, path, "patch", "200")
    headers = response.get("headers", {})
    vary = headers.get("Vary")
    assert vary, "CSRF-protected endpoints must document Vary header"
    example = vary.get("example", "")
    assert "Origin" in example, "Vary example must include Origin"


def test_openapi_documents_silent_session_continuity_flow():
    spec = _load_spec()
    operation = spec["paths"]["/auth/continue"]["get"]

    assert operation["security"] == []
    assert operation["operationId"] == "continueSession"
    params = {param["name"]: param for param in operation.get("parameters", [])}
    assert "redirect" in params
    assert "prompt=none" in operation["description"]
    assert "302" in operation["responses"]


def test_openapi_auth_continue_redirect_pattern_matches_runtime_contract():
    spec = _load_spec()
    operation = spec["paths"]["/auth/continue"]["get"]
    params = {param["name"]: param for param in operation.get("parameters", [])}
    pattern = re.compile(params["redirect"]["schema"]["pattern"])

    assert pattern.fullmatch("/learning/courses/course-1?module=module-7")
    assert not pattern.fullmatch("//evil.example")
    assert not pattern.fullmatch("/../admin")
    assert not pattern.fullmatch("/learning?next=https://evil.example")


def test_openapi_documents_auth_callback_query_invariant():
    spec = _load_spec()
    operation = spec["paths"]["/auth/callback"]["get"]

    params = {param["name"]: param for param in operation.get("parameters", [])}
    assert params["state"]["required"] is True
    assert params["code"]["required"] is False
    assert params["error"]["required"] is False

    query_contract = operation.get("x-gustav-query-contract")
    assert query_contract == {
        "required": ["state"],
        "oneOf": [{"required": ["code"]}, {"required": ["error"]}],
        "not": {"required": ["code", "error"]},
    }


def test_openapi_documents_direct_keycloak_registration_endpoint():
    spec = _load_spec()
    operation = spec["paths"]["/auth/register"]["get"]

    assert "/protocol/openid-connect/registrations" in operation["description"]
    assert "kc_action=register" not in operation["description"]
