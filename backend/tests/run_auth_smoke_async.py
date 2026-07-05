"""
Async standalone smoke check using httpx.AsyncClient against the ASGI app.
"""
import importlib
import anyio
import httpx
from httpx import ASGITransport

main = importlib.import_module("backend.web.main")


async def run_smoke() -> int:
    app = main.create_app_auth_only()
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
    raise SystemExit(anyio.run(run_smoke))
