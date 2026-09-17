"""No tokens, OIDC secrets or independent sessions belong in SvelteKit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_frontend_has_only_shared_cookie_transport():
    server = ROOT / "frontend/src/lib/server"
    assert not (server / "session.ts").exists()
    assert not (server / "backend-auth.ts").exists()
    api = (server / "api.ts").read_text()
    assert "gustav_session" in api
    assert "refresh_token" not in api and "accessToken" not in api
    assert "getRequestEvent().request" in api
