"""Contract tests for the SvelteKit-owned BFF token session."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_owns_server_side_token_session() -> None:
    session_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "session.ts"
    auth_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "backend-auth.ts"
    api_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "api.ts"

    assert session_helper_path.is_file(), f"Missing BFF session helper: {session_helper_path}"

    session_src = session_helper_path.read_text(encoding="utf-8")
    auth_src = auth_helper_path.read_text(encoding="utf-8")
    api_src = api_helper_path.read_text(encoding="utf-8")

    assert "gustav_bff_session" in session_src
    assert "Map<string" in session_src
    assert "accessToken" in session_src
    assert "refreshToken" in session_src
    assert "idToken" in session_src
    assert "cookies.set" in session_src
    assert "cookies.delete" in session_src

    assert "createTokenSession" in auth_src
    assert "clearTokenSession" in auth_src
    assert "jwtVerify" in auth_src
    assert "Bearer session:" not in auth_src

    assert "buildBackendAuthorizationHeader" in api_src
    assert "Bearer session:" not in api_src


def test_frontend_refreshes_expiring_token_sessions_before_backend_calls() -> None:
    session_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "session.ts"
    api_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "api.ts"

    session_src = session_helper_path.read_text(encoding="utf-8")
    api_src = api_helper_path.read_text(encoding="utf-8")

    assert "readFreshTokenSession" in session_src
    assert "grant_type" in session_src
    assert "refresh_token" in session_src
    assert "TOKEN_SESSIONS.set" in session_src
    assert "clearFrontendSessionCookie" in session_src

    assert "readFreshTokenSession" in api_src
