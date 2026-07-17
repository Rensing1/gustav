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
import re
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv  # type: ignore
    if os.getenv("RUN_E2E", "0") == "1":
        load_dotenv()
except Exception:
    pass


def _configure_requests_tls_for_local_e2e() -> None:
    """Require verified HTTPS for the production-like E2E profile.

    Caddy's local root CA is copied to the host by `make test-e2e`. Requests
    reads it through `REQUESTS_CA_BUNDLE`; no process-wide monkeypatch is used.
    """
    if os.getenv("RUN_E2E", "0") != "1":
        return
    if os.getenv("E2E_VERIFY_TLS") != "1":
        raise pytest.UsageError("E2E_VERIFY_TLS=1 is required when RUN_E2E=1")
    bundle = os.getenv("REQUESTS_CA_BUNDLE", "").strip()
    bundle_path = Path(bundle) if bundle else None
    if bundle_path is None or not bundle_path.is_file() or bundle_path.stat().st_size == 0:
        raise pytest.UsageError(
            "REQUESTS_CA_BUNDLE must point to the non-empty Caddy root CA; run `make test-e2e`"
        )


_configure_requests_tls_for_local_e2e()


# Ensure backend/web is importable if needed by E2E helpers
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


def _derive_e2e_email_domain() -> str:
    """Resolve a deterministic test email domain for local E2E users.

    Priority:
    1) `E2E_EMAIL_DOMAIN` (explicit override)
    2) first entry in `ALLOWED_REGISTRATION_DOMAINS` (e.g. "@school.example")
    3) fallback `example.com`
    """
    explicit = str(os.getenv("E2E_EMAIL_DOMAIN", "") or "").strip()
    if explicit:
        if explicit.startswith("@"):
            explicit = explicit[1:]
        if re.match(r"^[A-Za-z0-9.-]+$", explicit):
            return explicit.lower()

    allowed = str(os.getenv("ALLOWED_REGISTRATION_DOMAINS", "") or "").strip()
    if allowed:
        for raw in allowed.split(","):
            candidate = raw.strip()
            if not candidate:
                continue
            if candidate.startswith("@"):
                candidate = candidate[1:]
            if re.match(r"^[A-Za-z0-9.-]+$", candidate):
                return candidate.lower()

    return "example.com"


if os.getenv("RUN_E2E", "0") == "1":
    os.environ.setdefault("E2E_EMAIL_DOMAIN", _derive_e2e_email_domain())


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
