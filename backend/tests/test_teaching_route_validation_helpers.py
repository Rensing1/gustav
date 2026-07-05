"""Contracts for pure Teaching route validation helpers."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
HELPERS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_validation.py"


def test_pure_teaching_validation_helpers_live_outside_teaching_hotspot() -> None:
    """Pure parsing helpers should be reusable without growing the route hotspot."""

    teaching = importlib.import_module("backend.web.routes.teaching")
    helpers = importlib.import_module("backend.web.routes.teaching_validation")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    helper_source = HELPERS_SOURCE.read_text(encoding="utf-8")

    assert "def _canonical_uuid(" not in teaching_source
    assert "def canonical_uuid(" in helper_source
    assert teaching._canonical_uuid is helpers.canonical_uuid
    assert teaching._safe_int is helpers.safe_int
    assert teaching._clamp_limit_offset is helpers.clamp_limit_offset


def test_teaching_validation_helpers_keep_existing_behavior() -> None:
    helpers = importlib.import_module("backend.web.routes.teaching_validation")

    assert helpers.canonical_uuid("00000000-0000-0000-0000-000000000000") == (
        "00000000-0000-0000-0000-000000000000"
    )
    assert helpers.safe_int("7") == 7
    assert helpers.safe_int("not-int") is None
    assert helpers.clamp_limit_offset(
        limit=0,
        offset="-4",
        default_limit=20,
        max_limit=50,
        zero_means_default=True,
    ) == (20, 0)
