"""
OpenAPI auth & CSRF contract regression tests.

Why:
- CSRF-geschützte Write-Endpunkte sollen `Vary: Origin` deklarieren, damit
  Reverse-Proxies keine Antworten zwischen Origins teilen.
"""
from __future__ import annotations

from pathlib import Path
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
