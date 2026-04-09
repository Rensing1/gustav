"""Contract tests for the SvelteKit auth bridge.

Why:
    The browser must enter the auth flow through the new SvelteKit app. These
    tests lock the repo into frontend-owned OIDC routes instead of the old
    FastAPI session bridge.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_auth_bridge_routes() -> None:
    helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "backend-auth.ts"
    register_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "register" / "+page.svelte"
    register_page_server_path = REPO_ROOT / "frontend" / "src" / "routes" / "register" / "+page.server.ts"
    forgot_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "forgot-password" / "+page.svelte"
    forgot_page_server_path = REPO_ROOT / "frontend" / "src" / "routes" / "forgot-password" / "+page.server.ts"
    login_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "login" / "+server.ts"
    register_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "register" / "+server.ts"
    forgot_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "forgot" / "+server.ts"
    logout_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "logout" / "+server.ts"
    callback_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "callback" / "+server.ts"
    success_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "auth" / "logout" / "success" / "+page.svelte"

    for path in (
        helper_path,
        register_page_path,
        register_page_server_path,
        forgot_page_path,
        forgot_page_server_path,
        login_path,
        register_path,
        forgot_path,
        logout_path,
        callback_path,
        success_page_path,
    ):
        assert path.is_file(), f"Missing SvelteKit auth bridge file: {path}"

    helper_src = helper_path.read_text(encoding="utf-8")
    assert "protocol/openid-connect/auth" in helper_src
    assert "protocol/openid-connect/token" in helper_src
    assert "reset-credentials" in helper_src
    assert "kc_action" in helper_src
    assert "isAllowedRegistrationEmail" in helper_src
    assert "jwtVerify" in helper_src
    assert "/api/app/session-sync" in helper_src
    assert 'buildApiUrl("/auth/logout")' in helper_src or "buildApiUrl('/auth/logout')" in helper_src
    assert "headers.append(\"set-cookie\"" in helper_src or "headers.append('set-cookie'" in helper_src

    register_page_src = register_page_path.read_text(encoding="utf-8")
    register_page_server_src = register_page_server_path.read_text(encoding="utf-8")
    forgot_page_src = forgot_page_path.read_text(encoding="utf-8")
    forgot_page_server_src = forgot_page_server_path.read_text(encoding="utf-8")

    assert 'action="/register"' in register_page_src
    assert "Schul-E-Mail" in register_page_src
    assert "/auth/register" in register_page_server_src
    assert "invalid_email_domain" in register_page_server_src
    assert "ALLOWED_REGISTRATION_DOMAINS" in register_page_server_src
    assert 'form.get("redirect")' in register_page_server_src or "form.get('redirect')" in register_page_server_src
    assert 'params.set("redirect", redirectPath)' in register_page_server_src or "params.set('redirect', redirectPath)" in register_page_server_src

    assert 'action="/forgot-password"' in forgot_page_src
    assert "Passwort vergessen" in forgot_page_src
    assert "/auth/forgot" in forgot_page_server_src

    assert "startLoginFlow" in login_path.read_text(encoding="utf-8")
    assert "startRegisterFlow" in register_path.read_text(encoding="utf-8")
    assert "startForgotFlow" in forgot_path.read_text(encoding="utf-8")
    assert "handleLogout" in logout_path.read_text(encoding="utf-8")
    assert "handleAuthCallback" in callback_path.read_text(encoding="utf-8")

    success_page = success_page_path.read_text(encoding="utf-8")
    assert "/auth/login" in success_page
    assert "Erneut anmelden" in success_page
