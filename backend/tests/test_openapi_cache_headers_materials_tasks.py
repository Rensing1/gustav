"""
OpenAPI contract — Cache-Control headers on materials/tasks list endpoints.

Ensures 200 responses for the section-scoped list endpoints document
`Cache-Control` header to enforce privacy in clients/proxies.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def test_openapi_tasks_list_has_cache_header():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    op = spec["paths"]["/api/teaching/units/{unit_id}/sections/{section_id}/tasks"]["get"]
    headers = op["responses"]["200"].get("headers", {})
    assert "Cache-Control" in headers


def test_openapi_materials_list_has_cache_header():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    op = spec["paths"]["/api/teaching/units/{unit_id}/sections/{section_id}/materials"]["get"]
    headers = op["responses"]["200"].get("headers", {})
    assert "Cache-Control" in headers

