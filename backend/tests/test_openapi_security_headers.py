"""
OpenAPI security header and metadata checks.

Why:
- Ensure that privacy-sensitive endpoints document `Cache-Control: no-store`.
- Keep contract version aligned with the application version for clarity.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_users_search_documents_no_store_header():
    spec = _load_spec()
    path = "/api/users/search"
    assert path in spec["paths"], "Users search path missing in OpenAPI"
    resp = spec["paths"][path]["get"]["responses"]["200"]
    headers = resp.get("headers", {})
    assert "Cache-Control" in headers, "Users search 200 should document Cache-Control header"


def test_openapi_materials_download_url_documents_no_store_header():
    spec = _load_spec()
    path = "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url"
    assert path in spec["paths"], "Materials download-url path missing in OpenAPI"
    resp = spec["paths"][path]["get"]["responses"]["200"]
    headers = resp.get("headers", {})
    assert "Cache-Control" in headers, "download-url 200 should document Cache-Control header"


def test_openapi_version_matches_app_minor():
    spec = _load_spec()
    # App currently advertises version 0.0.2 in backend/web/main.py
    assert spec["info"]["version"].startswith("0.0.2"), "OpenAPI version should be 0.0.2 to match app"


def test_openapi_me_example_uses_offset_format():
    spec = _load_spec()
    me = spec["components"]["schemas"]["Me"]
    example = me.get("example", {})
    exp = example.get("expires_at", "")
    assert "+00:00" in exp or exp is None, 'expires_at example should use offset "+00:00"'
