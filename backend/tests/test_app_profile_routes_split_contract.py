"""Contracts for keeping app profile routes outside the app-route hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_profile_routes_live_in_focused_router_module() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    profile_routes = importlib.import_module("backend.web.routes.app_profile_routes")

    for route in profile_routes.app_profile_router.routes:
        assert route.endpoint.__module__ == profile_routes.__name__
        assert not hasattr(app_routes, route.endpoint.__name__)


def test_profile_routes_have_no_dynamic_facade_or_global_repair_dependency() -> None:
    source = (REPO_ROOT / "backend/web/routes/app_profile_routes.py").read_text(encoding="utf-8")
    for forbidden in ("_app_module", "sys.modules", "importlib", "__globals__", "from backend.web.routes.app import"):
        assert forbidden not in source


def test_profile_use_cases_do_not_import_the_web_adapter() -> None:
    for name in ("profile.py", "profile_helpers.py"):
        source = (REPO_ROOT / "backend/identity_access" / name).read_text(encoding="utf-8")
        assert "backend.web" not in source
        assert "fastapi" not in source


def test_app_hotspot_no_longer_defines_profile_route_handlers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "app.py").read_text(encoding="utf-8")

    assert "async def get_app_profile(" not in source
    assert "async def patch_profile_display_name(" not in source
    assert "async def patch_profile_name(" not in source
    assert "async def list_profile_cli_tokens(" not in source
    assert "async def create_profile_cli_token(" not in source
    assert "async def revoke_profile_cli_token(" not in source


def test_profile_router_owns_profile_paths() -> None:
    profile_routes = importlib.import_module("backend.web.routes.app_profile_routes")

    paths = {getattr(route, "path", "") for route in profile_routes.app_profile_router.routes}

    assert "/api/app/profile" in paths
    assert "/api/app/profile/display-name" in paths
    assert "/api/app/profile/name" in paths
    assert "/api/app/profile/cli-tokens" in paths
    assert "/api/app/profile/cli-tokens/{token_id}" in paths
