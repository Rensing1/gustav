"""
Minimal smoke test to ensure TestClient and the auth-only app work.

Focuses solely on GET /auth/login redirect behavior to isolate pytest hangs.
"""

from fastapi.testclient import TestClient
from pathlib import Path
import sys

# Import the auth-only app factory directly to avoid broader imports
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from main import create_app_auth_only  # type: ignore


def test_auth_login_redirects():
    app = create_app_auth_only()
    client = TestClient(app)
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    assert "location" in resp.headers
