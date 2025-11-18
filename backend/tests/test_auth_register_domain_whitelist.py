"""
Auth registration: environment-driven domain whitelist for login_hint.

Why:
    To keep self-service registration limited to school accounts (e.g. @gymalf.de),
    the /auth/register endpoint must reject disallowed email domains when the
    allow-list is configured via ALLOWED_REGISTRATION_DOMAINS.

Scope:
    - Allowed domain → normal redirect to Keycloak
    - Missing login_hint → unchanged behavior (redirect)
    - Disallowed/invalid email → 400 with Error payload and no redirect
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_register_allows_allowed_domain_when_env_configured(monkeypatch: pytest.MonkeyPatch):
    """Given a whitelisted domain, /auth/register should still redirect."""
    import sys

    sys.path.insert(0, str(WEB_DIR))
    import main  # type: ignore

    # Configure allow-list and ensure no stray value from the host leaks in.
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@gymalf.de")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=alice@gymalf.de", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert loc, "Expected redirect location for allowed domain"
    qs = parse_qs(urlparse(loc).query)
    # login_hint should be propagated unchanged to Keycloak
    assert qs.get("login_hint") == ["alice@gymalf.de"]


@pytest.mark.anyio
async def test_register_allows_mixed_case_and_whitespace(monkeypatch: pytest.MonkeyPatch):
    """Domains and login_hint should be handled case-insensitively and trimmed."""
    import sys

    sys.path.insert(0, str(WEB_DIR))
    import main  # type: ignore

    # Leading/trailing whitespace and mixed case in env variable
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "  @GymALF.de  ")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=Bob@GYMalf.DE", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert loc
    qs = parse_qs(urlparse(loc).query)
    assert qs.get("login_hint") == ["Bob@GYMalf.DE"]


@pytest.mark.anyio
async def test_register_without_login_hint_behaves_as_before(monkeypatch: pytest.MonkeyPatch):
    """Missing login_hint should not trigger domain validation."""
    import sys

    sys.path.insert(0, str(WEB_DIR))
    import main  # type: ignore

    # Even with an allow-list configured, missing login_hint should pass through.
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@gymalf.de")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers.get("location")


@pytest.mark.anyio
async def test_register_rejects_disallowed_domain(monkeypatch: pytest.MonkeyPatch):
    """Disallowed domain in login_hint should produce 400 with config-based error."""
    import sys

    sys.path.insert(0, str(WEB_DIR))
    import main  # type: ignore

    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@gymalf.de")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=mallory@gmail.com", follow_redirects=False)

    assert resp.status_code == 400
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "HX-Request"
    body = resp.json()
    assert body.get("error") == "invalid_email_domain"
    assert body.get("detail") == (
        "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt. Erlaubte Domains: @gymalf.de"
    )


@pytest.mark.anyio
async def test_register_rejects_invalid_email(monkeypatch: pytest.MonkeyPatch):
    """Clearly invalid email in login_hint should be treated like a disallowed domain."""
    import sys

    sys.path.insert(0, str(WEB_DIR))
    import main  # type: ignore

    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@gymalf.de")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=not-an-email", follow_redirects=False)

    assert resp.status_code == 400
    body = resp.json()
    assert body.get("error") == "invalid_email_domain"
    assert body.get("detail") == (
        "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt. Erlaubte Domains: @gymalf.de"
    )
