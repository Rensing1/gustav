"""
OpenAPI contract: GET /api/teaching/units/{unit_id}

Validates that the GET operation is present under the correct path and uses
authorOnly semantics for permissions.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def test_units_get_path_and_permissions_present():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))

    path = "/api/teaching/units/{unit_id}"
    assert path in spec["paths"], "units path missing in OpenAPI"
    assert "get" in spec["paths"][path], "GET missing for units in OpenAPI"
    perms = spec["paths"][path]["get"].get("x-permissions", {})
    assert perms.get("requiredRole") == "teacher"
    assert perms.get("authorOnly") is True

