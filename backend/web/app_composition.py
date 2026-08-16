"""FastAPI app composition helpers.

Why:
    `backend.web.main` still owns many legacy route handlers, but app shell
    creation, static mounting, and router inclusion are composition concerns.
    Keeping them here is the first step toward a smaller `main.py`.
"""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import sys
from weakref import WeakSet

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

_REGISTERED_APPS: WeakSet[FastAPI] = WeakSet()


def running_under_pytest() -> bool:
    """Detect whether the process is a pytest run or collection.

    Why:
        Runtime bootstrap must not load `.env` or execute deployment startup
        guards during unit-test collection. Tests provide their own environment
        and should remain deterministic.
    """

    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    if any(name == "pytest" or name.startswith("pytest.") for name in sys.modules):
        return True
    if any(name == "_pytest" or name.startswith("_pytest.") for name in sys.modules):
        return True
    if any("pytest" in (arg or "").lower() for arg in sys.argv):
        return True
    return False


def should_load_dotenv() -> bool:
    """Return whether runtime bootstrap should load a local `.env` file."""

    if running_under_pytest():
        return False
    flag = (os.getenv("GUSTAV_ENABLE_DOTENV", "true") or "").strip().lower()
    return flag in ("1", "true", "yes")


def bootstrap_runtime_environment() -> None:
    """Load runtime environment and run deployment startup guards.

    This function intentionally stays free of route registration concerns. It
    is called by `backend.web.main` before stores and OIDC clients are built.
    """

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv is not None and should_load_dotenv():
        load_dotenv()

    if running_under_pytest():
        return

    from backend.web import config

    config.ensure_secure_config_on_startup()


def create_app_shell() -> FastAPI:
    """Create the base FastAPI shell with GUSTAV metadata."""

    app = FastAPI(
        title="GUSTAV",
        description="KI-gestützte Lernplattform",
        version="0.0.4",
    )
    _REGISTERED_APPS.add(app)
    return app


def iter_registered_apps() -> tuple[FastAPI, ...]:
    """Return live app shells created in this Python process."""

    return tuple(_REGISTERED_APPS)


def mount_static_files(app: FastAPI, static_dir: Path) -> None:
    """Mount static web assets at `/static`."""

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def include_core_routers(app: FastAPI, routers: Iterable[APIRouter]) -> None:
    """Include the core FastAPI routers in deterministic order."""

    for router in routers:
        app.include_router(router)
