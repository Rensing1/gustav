"""
OpenAPI contract — guard against invalid 3.0 `type: null` usage.

Why:
    OAS 3.0 doesn't allow `type: null`. Use `nullable: true` instead.
"""
from __future__ import annotations

from pathlib import Path


def test_no_type_null_in_openapi_contract() -> None:
    text = Path("api/openapi.yml").read_text(encoding="utf-8")
    assert "type: 'null'" not in text and "type: null" not in text

