"""
Learning routes should use centralized storage config, not read env directly.

TDD: This test monkeypatches the central config getter to a sentinel value that
differs from the environment. It expects the learning adapter's `_storage_bucket()`
to reflect the centralized config.

Expected to fail until learning routes delegate to backend.storage.config.
"""
from __future__ import annotations

import importlib
import os


def test_learning_storage_bucket_prefers_central_config(monkeypatch):
    # Set env to a different value than our sentinel
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "subs-env")

    # Prepare central config with a sentinel return value
    import backend.storage.config as cfg
    monkeypatch.setattr(cfg, "get_submissions_bucket", lambda: "subs-cfg", raising=True)

    # Reload learning routes to pick up behavior. Use alias-friendly name
    # because the module registers both `routes.learning` and
    # `backend.web.routes.learning`.
    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))
    import routes.learning as learning

    # Expect the learning adapter to use central config value
    assert learning._storage_bucket() == "subs-cfg"
