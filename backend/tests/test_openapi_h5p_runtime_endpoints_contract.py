"""
OpenAPI contract test: H5P runtime endpoints (/h5p/ajax, /h5p/finishedData).

Why:
    The embedded H5P player uses cookie-authenticated runtime endpoints for
    translations and finished reporting. These endpoints are security-relevant
    (CSRF + role checks) and must be visible in the API contract for auditing.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_exposes_h5p_ajax_and_finisheddata_paths() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}
    assert "/h5p/ajax" in paths
    assert "/h5p/finishedData" in paths


def test_h5p_ajax_requires_cookie_auth_and_action_param() -> None:
    spec = _load_spec()
    post_op = spec["paths"]["/h5p/ajax"]["post"]
    assert post_op.get("security"), "H5P ajax must require cookie auth"
    params = post_op.get("parameters") or []
    action = next(p for p in params if p.get("name") == "action")
    assert action.get("in") == "query"
    assert action.get("required") is True
    responses = post_op.get("responses") or {}
    for code in ("200", "400", "401", "403", "500"):
        assert code in responses, f"missing response {code} for /h5p/ajax"


def test_h5p_finisheddata_requires_cookie_auth_and_has_success_response() -> None:
    spec = _load_spec()
    post_op = spec["paths"]["/h5p/finishedData"]["post"]
    assert post_op.get("security"), "H5P finishedData must require cookie auth"
    responses = post_op.get("responses") or {}
    assert "200" in responses
    schema = (
        responses["200"]
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    assert (schema.get("properties") or {}).get("success"), "200 response must contain {success: boolean}"

