"""
Pytest configuration for E2E tests.

Loads .env so that KC_BASE/WEB_BASE/KEYCLOAK_ADMIN etc. are taken from the
project's environment file, matching docker-compose settings.
"""
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Ensure backend/web is importable if needed by E2E helpers
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

