"""
OpenAPI contract — Cache-Control headers on list endpoints.

Validates that 200 responses for units list and sections list document
`Cache-Control` header to enforce privacy in clients/proxies.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def test_openapi_units_list_has_cache_header():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    op = spec["paths"]["/api/teaching/units"]["get"]
    headers = op["responses"]["200"].get("headers", {})
    assert "Cache-Control" in headers


def test_openapi_sections_list_has_cache_header():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    op = spec["paths"]["/api/teaching/units/{unit_id}/sections"]["get"]
    headers = op["responses"]["200"].get("headers", {})
    assert "Cache-Control" in headers

