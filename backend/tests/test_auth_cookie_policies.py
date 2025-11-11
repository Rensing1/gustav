"""
Cookie policy tests to ensure host-only cookies and consistent flags.

Goals:
- After /auth/callback, Set-Cookie for `gustav_session` must NOT include a
  Domain attribute (host-only cookie → avoids leakage across hosts).
- Einheitlich (dev = prod): SameSite=strict, Secure immer.

We mock token exchange and verification to avoid external dependencies.
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _install_fake_oidc_and_verifier(monkeypatch: pytest.MonkeyPatch):
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    def ok_claims(id_token: str, cfg: object):
        return {
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", ok_claims)


@pytest.mark.anyio
async def test_callback_sets_host_only_cookie_dev(monkeypatch: pytest.MonkeyPatch):
    _install_fake_oidc_and_verifier(monkeypatch)
    # Dev mode for predictable flags
    monkeypatch.setattr(main.SETTINGS, "_env_override", "dev", raising=False)

    # Fresh state store per run
    from identity_access.stores import StateStore, SessionStore
    monkeypatch.setattr(main, "STATE_STORE", StateStore())
    monkeypatch.setattr(main, "SESSION_STORE", SessionStore())
    rec = main.STATE_STORE.create(code_verifier="v")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)

    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    # Host-only: no Domain attribute present
    assert "Domain=" not in sc and "domain=" not in sc
    # Einheitliche Flags (auch in dev): Secure + SameSite=strict
    assert "SameSite=strict" in sc
    assert "Secure" in sc


@pytest.mark.anyio
async def test_callback_sets_host_only_cookie_prod(monkeypatch: pytest.MonkeyPatch):
    _install_fake_oidc_and_verifier(monkeypatch)
    # Prod mode for hardened flags
    monkeypatch.setattr(main.SETTINGS, "_env_override", "prod", raising=False)

    from identity_access.stores import StateStore, SessionStore
    monkeypatch.setattr(main, "STATE_STORE", StateStore())
    monkeypatch.setattr(main, "SESSION_STORE", SessionStore())
    rec = main.STATE_STORE.create(code_verifier="v")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)

    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    # Host-only cookie (no Domain attribute) even in prod
    assert "Domain=" not in sc and "domain=" not in sc
    assert "SameSite=strict" in sc
    assert "Secure" in sc
