"""Contracts for keeping internal Learning upload routes outside the hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_internal_upload_routes_live_in_focused_router_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    internal_routes = importlib.import_module("backend.web.routes.learning_internal_upload_routes")

    assert learning.internal_upload_stub is internal_routes.internal_upload_stub
    assert learning.internal_upload_proxy is internal_routes.internal_upload_proxy


def test_learning_hotspot_no_longer_defines_internal_upload_handlers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "async def internal_upload_stub(" not in source
    assert "async def internal_upload_proxy(" not in source


def test_internal_upload_router_owns_stub_and_proxy_paths() -> None:
    internal_routes = importlib.import_module("backend.web.routes.learning_internal_upload_routes")

    paths = {getattr(route, "path", "") for route in internal_routes.learning_internal_upload_router.routes}

    assert "/api/learning/internal/upload-stub" in paths
    assert "/api/learning/internal/upload-proxy" in paths
