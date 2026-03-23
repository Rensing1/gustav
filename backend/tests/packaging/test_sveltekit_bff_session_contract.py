"""Contract tests for the SvelteKit-owned BFF session cookie."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_owns_backend_session_mapping() -> None:
    session_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "session.ts"
    auth_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "backend-auth.ts"
    api_helper_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "api.ts"

    assert session_helper_path.is_file(), f"Missing BFF session helper: {session_helper_path}"

    session_src = session_helper_path.read_text(encoding="utf-8")
    auth_src = auth_helper_path.read_text(encoding="utf-8")
    api_src = api_helper_path.read_text(encoding="utf-8")

    assert "gustav_bff_session" in session_src
    assert "gustav_session" in session_src
    assert "cookies.set" in session_src
    assert "cookies.delete" in session_src

    assert "extractBackendSessionId" in auth_src
    assert "setFrontendSessionCookie" in auth_src
    assert "clearFrontendSessionCookie" in auth_src
    assert "\"set-cookie\"" not in auth_src.split("const FORWARDED_RESPONSE_HEADERS = [", 1)[1].split("];", 1)[0]

    assert "buildBackendSessionCookieHeader" in api_src
