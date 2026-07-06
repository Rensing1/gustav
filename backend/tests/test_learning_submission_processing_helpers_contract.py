"""Contracts for keeping Learning submission-processing helpers outside the hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_submission_processing_helpers_live_in_focused_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    processing = importlib.import_module("backend.web.routes.learning_submission_processing")

    assert learning._validate_submission_payload is processing.validate_submission_payload
    assert learning._dev_try_process_pdf is processing.dev_try_process_pdf


def test_learning_hotspot_no_longer_defines_submission_processing_helpers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "def _validate_submission_payload(" not in source
    assert "def _dev_try_process_pdf(" not in source
