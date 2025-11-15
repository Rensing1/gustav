"""
Central storage config should expose default max upload sizes with env overrides.

TDD: Fails until backend.storage.config provides getters for both domains.
"""
from __future__ import annotations

import importlib


def _reload_config():
    if 'backend.storage.config' in importlib.sys.modules:
        importlib.invalidate_caches()
        importlib.reload(importlib.import_module('backend.storage.config'))
    return importlib.import_module('backend.storage.config')


def test_limits_defaults(monkeypatch):
    monkeypatch.delenv('LEARNING_MAX_UPLOAD_BYTES', raising=False)
    monkeypatch.delenv('MATERIALS_MAX_UPLOAD_BYTES', raising=False)
    cfg = _reload_config()
    assert cfg.get_learning_max_upload_bytes() == 10 * 1024 * 1024
    assert cfg.get_materials_max_upload_bytes() == 20 * 1024 * 1024


def test_limits_env_overrides(monkeypatch):
    monkeypatch.setenv('LEARNING_MAX_UPLOAD_BYTES', '1234567')
    monkeypatch.setenv('MATERIALS_MAX_UPLOAD_BYTES', '7654321')
    cfg = _reload_config()
    assert cfg.get_learning_max_upload_bytes() == 1_234_567
    assert cfg.get_materials_max_upload_bytes() == 7_654_321


def test_limits_negative_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv('LEARNING_MAX_UPLOAD_BYTES', '-1')
    monkeypatch.setenv('MATERIALS_MAX_UPLOAD_BYTES', '-200')
    cfg = _reload_config()
    assert cfg.get_learning_max_upload_bytes() == 10 * 1024 * 1024
    assert cfg.get_materials_max_upload_bytes() == 20 * 1024 * 1024


def test_limits_are_capped_by_contract_maximum(monkeypatch):
    # Attempt to exceed documented OpenAPI maxima should clamp to contract values
    monkeypatch.setenv('LEARNING_MAX_UPLOAD_BYTES', str(50 * 1024 * 1024))
    monkeypatch.setenv('MATERIALS_MAX_UPLOAD_BYTES', str(100 * 1024 * 1024))
    cfg = _reload_config()
    assert cfg.get_learning_max_upload_bytes() == 10 * 1024 * 1024
    assert cfg.get_materials_max_upload_bytes() == 20 * 1024 * 1024
