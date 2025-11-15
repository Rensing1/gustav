"""
AI config — OLLAMA_BASE_URL host validation.

Ensures local/service hosts are accepted and weird/invalid hosts rejected.
"""
from __future__ import annotations

import importlib
import os
import pytest


def _reload():
    if 'backend.learning.config' in importlib.sys.modules:
        importlib.invalidate_caches()
        importlib.reload(importlib.import_module('backend.learning.config'))
    return importlib.import_module('backend.learning.config')


def test_accepts_local_and_service_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AI_BACKEND', 'local')
    for host in [
        'http://localhost:11434',
        'http://127.0.0.1:11434',
        'http://[::1]:11434',
        'http://ollama:11434',
        'http://ollama-1:11434',
    ]:
        monkeypatch.setenv('OLLAMA_BASE_URL', host)
        cfg = _reload()
        # Should not raise
        _ = cfg.load_ai_config()


def test_rejects_weird_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AI_BACKEND', 'local')
    # A set of invalid/unsafe hosts
    bad = [
        'http://exa mple:11434',
        'http://evil.example.com@:11434',
        'http://%00:11434',
        'file:///etc/passwd',
    ]
    for url in bad:
        monkeypatch.setenv('OLLAMA_BASE_URL', url)
        mod = _reload()
        with pytest.raises(ValueError):
            _ = mod.load_ai_config()
