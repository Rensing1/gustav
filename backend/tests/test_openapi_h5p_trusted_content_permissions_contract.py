"""
OpenAPI contract: H5P "trusted content" endpoints document teacher-only access.

Why:
    H5P library/content management endpoints deal with executable content and
    must be restricted to trusted roles. The OpenAPI contract should document
    this in a machine-readable way (`x-permissions`) so reviewers and clients
    can reason about authorization without reading server code.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_h5p_trusted_content_endpoints_are_teacher_only_in_openapi() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}

    expectations = [
        ("/h5p/editor/model", "get"),
        ("/h5p/libraries", "get"),
        ("/h5p/libraries/import", "post"),
        ("/h5p/contents/import", "post"),
        ("/h5p/contents", "post"),
        ("/h5p/contents/{content_id}", "patch"),
        ("/h5p/contents/{content_id}/export", "get"),
    ]

    for path, method in expectations:
        assert path in paths, f"missing {path} in openapi.yml"
        op = (paths[path] or {}).get(method)
        assert isinstance(op, dict), f"missing {method.upper()} {path} operation in openapi.yml"
        perms = op.get("x-permissions") or {}
        assert perms.get("requiredRole") == "teacher", f"{method.upper()} {path} must require teacher role"

