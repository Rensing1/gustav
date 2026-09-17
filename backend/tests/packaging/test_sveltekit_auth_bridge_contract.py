"""Only FastAPI owns browser OIDC endpoints after the coordinated cutover."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_backend_owns_oidc_and_frontend_only_renders():
    frontend = ROOT / "frontend/src"
    for endpoint in ("login", "register", "continue", "callback", "forgot", "password"):
        assert not (frontend / f"routes/auth/{endpoint}/+server.ts").exists()
    assert "/auth/register" in (frontend / "routes/register/+page.server.ts").read_text()
    assert (frontend / "routes/auth/logout/+page.svelte").exists()
    assert 'method="post"' in (frontend / "routes/auth/logout/+page.svelte").read_text()
    proxy = (ROOT / "reverse-proxy/Caddyfile").read_text()
    assert "/auth/callback" in proxy and "method POST" in proxy
