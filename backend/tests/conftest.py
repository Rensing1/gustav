import os
import sys
from pathlib import Path
import pytest

# Ensure we can import the FastAPI app from backend/web/main.py without changing packages
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from main import app  # type: ignore  # noqa: E402
from fastapi.testclient import TestClient  # type: ignore  # noqa: E402


@pytest.fixture(scope="function")
def client() -> TestClient:
    """ASGI test client for the FastAPI app.

    Keeps tests decoupled from packaging layout; we avoid modifying app code here.
    """
    return TestClient(app)
