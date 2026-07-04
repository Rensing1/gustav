"""
Auth registration: environment-driven domain whitelist for login_hint.

Why:
    To keep self-service registration limited to school accounts (e.g. @school.example),
    the /auth/register endpoint must reject disallowed email domains when the
    allow-list is configured via ALLOWED_REGISTRATION_DOMAINS.

Scope:
    - Allowed domain → normal redirect to Keycloak
    - Missing login_hint → unchanged behavior (redirect)
    - Disallowed/invalid email → 400 with Error payload and no redirect
"""

from __future__ import annotations

import importlib
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport

main = importlib.import_module("backend.web.main")


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_register_allows_allowed_domain_when_env_configured(monkeypatch: pytest.MonkeyPatch):
    """Given a whitelisted domain, /auth/register should still redirect."""
    # Configure allow-list and ensure no stray value from the host leaks in.
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=alice@school.example", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert loc, "Expected redirect location for allowed domain"
    qs = parse_qs(urlparse(loc).query)
    # login_hint should be propagated unchanged to Keycloak
    assert qs.get("login_hint") == ["alice@school.example"]


@pytest.mark.anyio
async def test_register_allows_mixed_case_and_whitespace(monkeypatch: pytest.MonkeyPatch):
    """Domains and login_hint should be handled case-insensitively and trimmed."""
    # Leading/trailing whitespace and mixed case in env variable
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "  @School.Example  ")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=Bob@SCHOOL.EXAMPLE", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert loc
    qs = parse_qs(urlparse(loc).query)
    assert qs.get("login_hint") == ["Bob@SCHOOL.EXAMPLE"]


@pytest.mark.anyio
async def test_register_without_login_hint_behaves_as_before(monkeypatch: pytest.MonkeyPatch):
    """Missing login_hint should not trigger domain validation."""
    # Even with an allow-list configured, missing login_hint should pass through.
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers.get("location")


@pytest.mark.anyio
async def test_register_rejects_disallowed_domain(monkeypatch: pytest.MonkeyPatch):
    """Disallowed domain in login_hint should produce 400 with config-based error."""
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=mallory@gmail.com", follow_redirects=False)

    assert resp.status_code == 400
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "HX-Request"
    body = resp.json()
    assert body.get("error") == "invalid_email_domain"
    assert body.get("detail") == (
        "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt. Erlaubte Domains: @school.example"
    )


@pytest.mark.anyio
async def test_register_rejects_invalid_email(monkeypatch: pytest.MonkeyPatch):
    """Clearly invalid email in login_hint should be treated like a disallowed domain."""
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/register?login_hint=not-an-email", follow_redirects=False)

    assert resp.status_code == 400
    body = resp.json()
    assert body.get("error") == "invalid_email_domain"
    assert body.get("detail") == (
        "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt. Erlaubte Domains: @school.example"
    )
