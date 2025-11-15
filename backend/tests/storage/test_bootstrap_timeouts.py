"""
Storage bootstrap — HTTP timeouts and exception handling.

Expected:
  - ensure_buckets_from_env does not hang when network fails.
  - requests.get/post are called with conservative timeouts.
  - Function returns without raising, logging warnings is acceptable.
"""

from __future__ import annotations

import importlib
import time
from types import SimpleNamespace

import pytest
import requests


def test_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange environment for auto bootstrap
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "materials")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")

    calls: list[tuple[str, dict]] = []

    def _raise_timeout(*args, **kwargs):
        # Capture timeout arg for assertion
        calls.append(("get", kwargs))
        raise requests.exceptions.ConnectTimeout("boom")

    def _raise_timeout_post(*args, **kwargs):
        calls.append(("post", kwargs))
        raise requests.exceptions.ReadTimeout("boom")

    # Patch requests.get/post to raise timeouts
    monkeypatch.setattr(requests, "get", _raise_timeout, raising=True)
    monkeypatch.setattr(requests, "post", _raise_timeout_post, raising=True)

    # Act
    t0 = time.time()
    mod = importlib.import_module("backend.storage.bootstrap")
    # Reload to ensure fresh functions
    importlib.reload(mod)
    ok = mod.ensure_buckets_from_env()  # type: ignore[attr-defined]
    dt = time.time() - t0

    # Assert: function completes quickly and returns a boolean
    assert isinstance(ok, bool)
    assert dt < 2.0

    # Assert: at least one GET and one POST attempted with timeouts
    kinds = [k for (k, _kw) in calls]
    assert "get" in kinds
    assert "post" in kinds
    # Every call must include a timeout tuple (connect, read)
    for _k, kw in calls:
        assert "timeout" in kw
        to = kw["timeout"]
        assert isinstance(to, tuple) and len(to) == 2
        assert to[0] <= 5 and to[1] <= 15

