"""Contracts for keeping app profile routes outside the app-route hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_profile_routes_live_in_focused_router_module() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    profile_routes = importlib.import_module("backend.web.routes.app_profile_routes")

    assert app_routes.get_app_profile is profile_routes.get_app_profile
    assert app_routes.patch_profile_display_name is profile_routes.patch_profile_display_name
    assert app_routes.patch_profile_name is profile_routes.patch_profile_name
    assert app_routes.list_profile_cli_tokens is profile_routes.list_profile_cli_tokens
    assert app_routes.create_profile_cli_token is profile_routes.create_profile_cli_token
    assert app_routes.revoke_profile_cli_token is profile_routes.revoke_profile_cli_token


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
