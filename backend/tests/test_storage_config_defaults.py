"""
Unit tests for centralized storage config defaults.

Why:
    Prevent scattered hard-coded defaults. A single config module should
    define the canonical default bucket names and env overrides.

Behavior (BDD):
    Given no relevant env vars are set,
    When importing the storage config module,
    Then materials bucket defaults to "materials" and submissions to "submissions".

    Given env vars override values,
    When calling the getters,
    Then they reflect the override values.

This test should fail until `backend/storage/config.py` exists and implements
the expected API.
"""
from __future__ import annotations

import os
import importlib


def _reload_config():
    if 'backend.storage.config' in importlib.sys.modules:
        importlib.invalidate_caches()
        importlib.reload(importlib.import_module('backend.storage.config'))
    return importlib.import_module('backend.storage.config')


def test_defaults_without_env(monkeypatch):
    # Ensure env is clean
    monkeypatch.delenv('SUPABASE_STORAGE_BUCKET', raising=False)
    monkeypatch.delenv('LEARNING_STORAGE_BUCKET', raising=False)

    cfg = _reload_config()
    assert getattr(cfg, 'MATERIALS_BUCKET_DEFAULT', None) == 'materials'
    assert getattr(cfg, 'SUBMISSIONS_BUCKET_DEFAULT', None) == 'submissions'
    assert cfg.get_materials_bucket() == 'materials'
    assert cfg.get_submissions_bucket() == 'submissions'


def test_env_overrides(monkeypatch):
    monkeypatch.setenv('SUPABASE_STORAGE_BUCKET', 'mat-dev')
    monkeypatch.setenv('LEARNING_STORAGE_BUCKET', 'subs-dev')
    cfg = _reload_config()
    assert cfg.get_materials_bucket() == 'mat-dev'
    assert cfg.get_submissions_bucket() == 'subs-dev'


def test_submissions_bucket_falls_back_to_legacy_env(monkeypatch):
    """Legacy LEARNING_SUBMISSIONS_BUCKET must stay supported for old deploys."""

    monkeypatch.delenv('LEARNING_STORAGE_BUCKET', raising=False)
    monkeypatch.setenv('LEARNING_SUBMISSIONS_BUCKET', 'legacy-subs')

    cfg = _reload_config()
    assert cfg.get_submissions_bucket() == 'legacy-subs'
