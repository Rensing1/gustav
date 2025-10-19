"""
Pytest configuration for backend tests.

Why: Force AnyIO to use the asyncio backend to avoid sandbox restrictions
that can affect the Trio backend (e.g., socketpair permission errors).
"""
import pytest
import sys
from pathlib import Path

# Load .env so E2E tests pick up credentials (KEYCLOAK_ADMIN, ...)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Ensure modules in backend/ and backend/web are importable across tests
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
WEB_DIR = BACKEND_DIR / "web"
for p in (str(BACKEND_DIR), str(WEB_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def anyio_backend():
    return "asyncio"
