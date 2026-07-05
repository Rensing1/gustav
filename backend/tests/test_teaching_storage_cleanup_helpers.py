"""Contracts for Teaching unit-delete storage cleanup helpers."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
CLEANUP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_storage_cleanup.py"


def test_unit_delete_storage_helpers_live_outside_teaching_hotspot() -> None:
    """Storage cleanup logic should not keep growing the Teaching route hotspot."""

    teaching = importlib.import_module("backend.web.routes.teaching")
    cleanup = importlib.import_module("backend.web.routes.teaching_storage_cleanup")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    cleanup_source = CLEANUP_SOURCE.read_text(encoding="utf-8")

    assert "def _metadata_page_keys(" not in teaching_source
    assert "def metadata_page_keys(" in cleanup_source
    assert teaching._metadata_page_keys is cleanup.metadata_page_keys
    assert teaching._unit_delete_storage_metadata_dsn is cleanup.unit_delete_storage_metadata_dsn


def test_metadata_page_keys_accepts_json_text_and_filters_empty_values() -> None:
    cleanup = importlib.import_module("backend.web.routes.teaching_storage_cleanup")

    assert cleanup.metadata_page_keys('{"page_keys": [" a ", "", null, "b"]}') == ["a", "b"]
    assert cleanup.metadata_page_keys({"page_keys": ["x", 42]}) == ["x", "42"]
    assert cleanup.metadata_page_keys("not-json") == []
    assert cleanup.metadata_page_keys({"page_keys": "not-a-list"}) == []


def test_delete_storage_objects_fails_closed_without_adapter_method() -> None:
    cleanup = importlib.import_module("backend.web.routes.teaching_storage_cleanup")

    try:
        cleanup.delete_storage_objects(object(), [("materials", "unit/file.pdf")])
    except RuntimeError as exc:
        assert str(exc) == "storage_adapter_not_configured"
    else:  # pragma: no cover - assertion branch
        raise AssertionError("delete_storage_objects must fail closed without delete_object")
