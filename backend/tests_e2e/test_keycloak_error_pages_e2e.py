"""
E2E regression tests for Keycloak error page rendering.

Why:
    Production observed HTTP 500 responses when Keycloak rendered GUSTAV error
    pages without optional context values such as pageRedirectUri. Static theme
    tests stayed green, so these checks exercise the real Keycloak renderer.
"""

from __future__ import annotations

import os
import time

import pytest
import requests


pytestmark = pytest.mark.e2e


KC_BASE = os.getenv("KC_BASE", os.getenv("KC_PUBLIC_BASE_URL", "https://id.localhost")).rstrip("/")
REALM = os.getenv("KC_REALM", "gustav")


def _assert_state_checker_cookie_is_hardened(response: requests.Response) -> None:
    """Assert cookie flags without logging the sensitive cookie value."""
    set_cookie = response.headers.get("Set-Cookie", "")
    lowered = set_cookie.lower()

    assert "kc_state_checker=" in lowered
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=lax" in lowered
    assert "domain=" not in lowered


def _wait_for_keycloak() -> None:
    """Fail clearly if the local Keycloak service is not reachable."""
    url = f"{KC_BASE}/realms/{REALM}"
    deadline = time.time() + int(os.getenv("E2E_READY_TIMEOUT_S", "20"))
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.5)

    pytest.fail(f"Keycloak was not reachable at {url}; last_error={last_error!r}")


@pytest.mark.parametrize(
    "path",
    [
        "/login-actions/authenticate",
        "/login-actions/action-token?key=expired",
    ],
)
def test_keycloak_error_flows_render_without_template_500(path: str) -> None:
    """Cookie-less and invalid-token flows must not turn theme recovery into HTTP 500."""
    _wait_for_keycloak()

    response = requests.get(f"{KC_BASE}/realms/{REALM}{path}", timeout=10)

    assert response.status_code == 400
    assert "text/html" in response.headers.get("Content-Type", "")
    assert "no-store" in response.headers.get("Cache-Control", "")
    assert response.headers.get("X-Content-Type-Options", "").lower() == "nosniff"
    assert response.headers.get("X-Frame-Options", "").upper() == "SAMEORIGIN"
    assert "max-age=" in response.headers.get("Strict-Transport-Security", "").lower()
    assert response.status_code != 500
    assert "HTTP 500 Internal Server Error" not in response.text
    assert "FreeMarker" not in response.text
    assert 'class="kc-gustav"' in response.text
    assert "Anmeldung nicht möglich" in response.text
    assert "/login-actions/authenticate" not in response.text
    assert "/login-actions/registration" not in response.text
    _assert_state_checker_cookie_is_hardened(response)
