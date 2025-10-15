"""
Async standalone smoke check using httpx.AsyncClient against the ASGI app.
"""
from pathlib import Path
import sys
import anyio
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
WEB_DIR = BACKEND_DIR / "web"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(WEB_DIR))

from main import create_app_auth_only  # type: ignore


async def main() -> int:
    app = create_app_auth_only()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/auth/login", follow_redirects=False)
    print("status:", resp.status_code)
    print("location header?", "location" in resp.headers)
    if resp.status_code == 302 and "location" in resp.headers:
        print("SMOKE: OK")
        return 0
    print("SMOKE: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(anyio.run(main))
