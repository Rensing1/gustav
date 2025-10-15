import os
import sys
from pathlib import Path
import pytest
import httpx
from httpx import ASGITransport

# Ensure we can import the app and identity_access without packaging
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
WEB_DIR = BACKEND_DIR / "web"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(WEB_DIR))

from main import create_app_auth_only  # type: ignore  # noqa: E402


@pytest.fixture()
def async_client():
    """Async HTTP client against the auth-only ASGI app using httpx.ASGITransport."""
    app = create_app_auth_only()
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        yield client
    finally:
        # Ensure the client is closed even if a test fails early
        try:
            import anyio
            anyio.run(client.aclose)
        except Exception:
            pass
