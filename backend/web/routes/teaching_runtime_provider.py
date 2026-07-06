"""Runtime wiring helpers for already-registered Teaching routes.

Why:
    Tests and local tooling sometimes reload ``backend.web.routes.teaching``
    while an existing FastAPI app still owns route callables from the previous
    module instance. These helpers retarget those old endpoint globals to the
    current repository or storage adapter without mixing this compatibility
    wiring into the route definitions themselves.
"""

from __future__ import annotations

import sys as _sys
from typing import Any

from fastapi.routing import APIRoute


def _registered_apps() -> list[Any]:
    """Return known FastAPI app instances that may contain Teaching routes."""

    apps: list[Any] = []
    main_module = _sys.modules.get("backend.web.main")
    app = getattr(main_module, "app", None) if main_module is not None else None
    if app is not None:
        apps.append(app)
    try:
        from backend.web.app_composition import iter_registered_apps

        apps.extend(iter_registered_apps())
    except Exception:
        pass
    return apps


def _teaching_route_endpoint_globals() -> list[dict[str, Any]]:
    """Collect globals dictionaries for registered Teaching route endpoints."""

    route_globals_list: list[dict[str, Any]] = []
    seen_apps: set[int] = set()
    for app in _registered_apps():
        app_id = id(app)
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        routes = getattr(app, "routes", None)
        if not routes:
            continue
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            if not str(getattr(route, "path", "")).startswith("/api/teaching"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict):
                route_globals_list.append(route_globals)
    return route_globals_list


def sync_route_storage_adapter(adapter: Any, *, override_active: bool) -> None:
    """Retarget already-registered Teaching route globals to the current adapter."""

    for route_globals in _teaching_route_endpoint_globals():
        if "STORAGE_ADAPTER" not in route_globals:
            continue
        route_globals["STORAGE_ADAPTER"] = adapter
        route_globals["_STORAGE_ADAPTER_OVERRIDE_ACTIVE"] = override_active
        bound_teaching = route_globals.get("teaching_routes")
        if bound_teaching is not None:
            setattr(bound_teaching, "STORAGE_ADAPTER", adapter)
            setattr(bound_teaching, "_STORAGE_ADAPTER_OVERRIDE_ACTIVE", override_active)


def sync_route_repo(repo: Any) -> None:
    """Retarget already-registered Teaching route globals to the current repo."""

    for route_globals in _teaching_route_endpoint_globals():
        if "_REPO" not in route_globals:
            continue
        route_globals["_REPO"] = repo
        route_globals["REPO"] = repo
        bound_teaching = route_globals.get("teaching_routes")
        if bound_teaching is not None:
            setattr(bound_teaching, "_REPO", repo)
            setattr(bound_teaching, "REPO", repo)
