"""
Teaching materials service should use centralized storage config for its
default bucket selection.

TDD: Monkeypatch the config getter to a sentinel distinct from env; expect
newly created MaterialsService to adopt the config value in its settings.

Expected to fail until materials service uses backend.storage.config.
"""
from __future__ import annotations

import importlib
import os


def test_teaching_materials_service_uses_central_config(monkeypatch):
    # Different env value to ensure we detect direct env reads
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "mat-env")

    import backend.storage.config as cfg
    monkeypatch.setattr(cfg, "get_materials_bucket", lambda: "mat-cfg", raising=True)

    # Reload module under test to avoid cached defaults
    if "backend.teaching.services.materials" in importlib.sys.modules:
        importlib.reload(importlib.import_module("backend.teaching.services.materials"))
    from backend.teaching.services.materials import MaterialsService

    svc = MaterialsService(repo=None)  # repo is not used for settings
    assert svc.settings.storage_bucket == "mat-cfg"

