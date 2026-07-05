"""Central pytest import-path bootstrap.

Why:
    PR 9 keeps pytest import setup in one place while the legacy test suite is
    migrated from flat imports to package-oriented imports. The target layout is
    the production layout: repository root on `sys.path`, imports via
    `backend.*`. The temporary compatibility paths below keep old tests running
    until legacy imports from `identity_access.*`, `teaching.*`, and related test
    scaffolding are fully removed.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
WEB_DIR = BACKEND_DIR / "web"
TESTS_DIR = BACKEND_DIR / "tests"

# Legacy compatibility for existing tests that still import through backend/web
# or backend as a top-level root. New tests should not add local sys.path hacks.
LEGACY_TEST_IMPORT_PATHS = (
    REPO_ROOT,
    BACKEND_DIR,
    WEB_DIR,  # legacy backend/web root
    TESTS_DIR,
)


def configure_test_import_paths() -> None:
    """Install the temporary pytest import roots in one deterministic place."""

    for path in LEGACY_TEST_IMPORT_PATHS:
        raw = str(path)
        if raw not in sys.path:
            sys.path.insert(0, raw)


ROUTE_ALIAS_MODULES: tuple[str, ...] = ()


def canonicalize_legacy_route_aliases() -> None:
    """Keep legacy route alias repair deterministic for existing tests.

    Why:
        Some legacy tests remove individual `sys.modules` entries and then
        re-import route packages under older alias names. Without this repair
        step, Python can create a second module instance whose globals drift
        from the FastAPI app.
        The production app does not need this; it is a temporary pytest bridge
        until flat route imports are gone.
    """

    configure_test_import_paths()
    if not ROUTE_ALIAS_MODULES:
        return

    routes_package = sys.modules.get("routes")
    for module_name in ROUTE_ALIAS_MODULES:
        package_module = importlib.import_module(f"backend.web.routes.{module_name}")
        sys.modules[f"routes.{module_name}"] = package_module
        if routes_package is not None:
            setattr(routes_package, module_name, package_module)
