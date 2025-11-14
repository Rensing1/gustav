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
import requests

try:
    from dotenv import load_dotenv  # type: ignore
    if os.getenv("RUN_E2E", "0") == "1":
        load_dotenv()
except Exception:
    pass


# Ensure backend/web is importable if needed by E2E helpers
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

def _derive_app_base() -> str:
    wb = os.getenv("WEB_BASE")
    if wb:
        return wb.rstrip("/")
    ru = os.getenv("REDIRECT_URI", "")
    if isinstance(ru, str) and ru:
        if "/auth/callback" in ru:
            return ru.split("/auth/callback")[0].rstrip("/")
        try:
            from urllib.parse import urlparse
            p = urlparse(ru)
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            pass
    return "https://app.localhost"


def _derive_kc_base() -> str:
    kb = os.getenv("KC_BASE")
    if kb:
        return kb.rstrip("/")
    pub = os.getenv("KC_PUBLIC_BASE_URL")
    if pub:
        return pub.rstrip("/")
    return "https://id.localhost"


def pytest_collection_modifyitems(config, items):
    """Gate E2E tests behind an explicit flag RUN_E2E=1.

    Rationale: Prevent accidental hangs/flakes by only running E2E when the
    developer intentionally enables them. No additional env toggles are used.
    """
    pkg_dir = Path(__file__).parent.resolve()
    if os.getenv("RUN_E2E", "0") == "1":
        return
    skip = pytest.mark.skip(reason="E2E tests disabled; set RUN_E2E=1 to enable")
    for item in items:
        try:
            if Path(str(item.fspath)).resolve().is_relative_to(pkg_dir):
                item.add_marker(skip)
        except Exception:
            if str(item.fspath).startswith(str(pkg_dir)):
                item.add_marker(skip)
