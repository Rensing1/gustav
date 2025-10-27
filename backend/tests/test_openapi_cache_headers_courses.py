"""
OpenAPI contract — Cache-Control header on courses list endpoint.

Validates that 200 responses for GET /api/teaching/courses document a
`Cache-Control` header to enforce privacy in clients/proxies.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def test_openapi_courses_list_has_cache_header():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    op = spec["paths"]["/api/teaching/courses"]["get"]
    headers = op["responses"]["200"].get("headers", {})
    assert "Cache-Control" in headers

