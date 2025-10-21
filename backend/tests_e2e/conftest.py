"""
Pytest configuration for E2E tests.

Behavior:
- Loads .env so that KC_BASE/WEB_BASE/KEYCLOAK_ADMIN etc. are taken from the
  project's environment file, matching docker-compose settings.
- Skips the entire E2E test suite unless RUN_E2E=1 is set. This keeps the
  default developer/CI workflow fast and deterministic. When running locally
  against docker-compose, export RUN_E2E=1 to enable these tests.
"""
import sys
from pathlib import Path
import os
import pytest

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# Ensure backend/web is importable if needed by E2E helpers
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

def pytest_collection_modifyitems(config, items):
    """Skip E2E tests in this package unless RUN_E2E=1 is set."""
    if os.getenv("RUN_E2E", "0") == "1":
        return
    pkg_dir = Path(__file__).parent.resolve()
    skip = pytest.mark.skip(reason="E2E tests disabled; set RUN_E2E=1 to enable")
    for item in items:
        try:
            if Path(str(item.fspath)).resolve().is_relative_to(pkg_dir):
                item.add_marker(skip)
        except Exception:
            # Fallback for Python <3.9 or non-path items
            if str(item.fspath).startswith(str(pkg_dir)):
                item.add_marker(skip)
