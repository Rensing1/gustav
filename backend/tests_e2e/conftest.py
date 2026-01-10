"""
Pytest configuration for E2E tests.

Behavior:
- Loads .env only when RUN_E2E=1 so that KC_BASE/WEB_BASE/KEYCLOAK_ADMIN etc. are
  taken from the project's environment file, matching docker-compose settings.
- Skips the entire E2E test suite unless RUN_E2E=1 is set. This keeps the
  default developer/CI workflow fast and deterministic. When running locally
  against docker-compose, export RUN_E2E=1 to enable these tests.
"""
import os
import sys
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv  # type: ignore
    if os.getenv("RUN_E2E", "0") == "1":
        load_dotenv()
except Exception:
    pass


def _configure_requests_tls_for_local_e2e() -> None:
    """
    E2E tests talk to `https://app.localhost` / `https://id.localhost` via Caddy.

    In the default local setup, Caddy uses a locally-generated certificate which
    is *not* trusted by Python's CA store inside the dev container.

    To keep E2E tests runnable without manual CA installation, we default to
    `verify=False` when RUN_E2E=1. If you do have a trusted CA bundle, set
    `E2E_VERIFY_TLS=1` to re-enable certificate verification.
    """
    if os.getenv("RUN_E2E", "0") != "1":
        return
    if os.getenv("E2E_VERIFY_TLS", "0") == "1":
        return
    try:
        import warnings
        import urllib3  # type: ignore
        from urllib3.exceptions import InsecureRequestWarning  # type: ignore
        urllib3.disable_warnings(InsecureRequestWarning)
        warnings.filterwarnings("ignore", category=InsecureRequestWarning)
    except Exception:
        pass
    try:
        import requests  # type: ignore
        from requests.sessions import Session  # type: ignore

        original_request = Session.request

        def request_with_insecure_default(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("verify", False)
            return original_request(self, method, url, **kwargs)

        Session.request = request_with_insecure_default  # type: ignore[assignment]
    except Exception:
        # If requests isn't available, individual tests may fail with a clearer error.
        return


_configure_requests_tls_for_local_e2e()


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

    Rationale: prevent accidental hangs/flakes by only running E2E when the
    developer intentionally enables them.
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
