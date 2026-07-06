"""Contracts for keeping Learning storage-validation helpers outside the hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_storage_validation_helpers_live_in_focused_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    storage_validation = importlib.import_module("backend.web.routes.learning_storage_validation")

    assert learning._verify_storage_object is storage_validation.verify_storage_object
    assert learning._load_local_storage_bytes_for_validation is storage_validation.load_local_storage_bytes_for_validation
    assert learning._download_bytes_with_limit is storage_validation.download_bytes_with_limit
    assert learning._load_storage_bytes_for_validation is storage_validation.load_storage_bytes_for_validation


def test_learning_hotspot_no_longer_defines_storage_validation_helpers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "def _verify_storage_object(" not in source
    assert "def _load_local_storage_bytes_for_validation(" not in source
    assert "async def _download_bytes_with_limit(" not in source
    assert "async def _load_storage_bytes_for_validation(" not in source
