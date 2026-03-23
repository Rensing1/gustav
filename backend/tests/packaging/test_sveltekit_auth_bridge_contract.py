"""Contract tests for the SvelteKit auth bridge.

Why:
    The browser must enter the auth flow through the new SvelteKit app even
    while FastAPI still owns the existing session implementation. These tests
    lock the repo into that bridging step.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_auth_bridge_routes() -> None:
    helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "backend-auth.ts"
    login_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "login" / "+server.ts"
    register_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "register" / "+server.ts"
    forgot_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "forgot" / "+server.ts"
    logout_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "logout" / "+server.ts"
    callback_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "callback" / "+server.ts"
    success_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "logout" / "success" / "+page.svelte"

    for path in (
        helper_path,
        login_path,
        register_path,
        forgot_path,
        logout_path,
        callback_path,
        success_page_path,
    ):
        assert path.is_file(), f"Missing SvelteKit auth bridge file: {path}"

    helper_src = helper_path.read_text(encoding="utf-8")
    assert "API_INTERNAL_BASE_URL" in helper_src
    assert "set-cookie" in helper_src
    assert "location" in helper_src

    assert '"/auth/login"' in login_path.read_text(encoding="utf-8")
    assert '"/auth/register"' in register_path.read_text(encoding="utf-8")
    assert '"/auth/forgot"' in forgot_path.read_text(encoding="utf-8")
    assert '"/auth/logout"' in logout_path.read_text(encoding="utf-8")
    assert '"/auth/callback"' in callback_path.read_text(encoding="utf-8")

    success_page = success_page_path.read_text(encoding="utf-8")
    assert "/auth/login" in success_page
    assert "Erneut anmelden" in success_page
