"""
OpenAPI contract: Module section releases listing must be owner-only.

Validates that GET /api/teaching/courses/{course_id}/modules/{module_id}/sections/releases
declares x-permissions with requiredRole=teacher and ownerOnly=true.
"""
from __future__ import annotations

from pathlib import Path
import yaml


def test_module_releases_owner_only_permission():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    path = "/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases"
    assert path in spec["paths"], "module releases path missing in OpenAPI"
    op = spec["paths"][path]["get"]
    perms = op.get("x-permissions", {})
    assert perms.get("requiredRole") == "teacher"
    assert perms.get("ownerOnly") is True, "ownerOnly should be true for module releases"

