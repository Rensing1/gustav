"""
Auth UI page rendering tests for structured SSR forms.

We assert that the flag-enabled GET routes render consistent form markup
using our components (FormField wrappers, labels, inputs, submit button)
and that pages are served within the Layout wrapper.
"""

import re
from pathlib import Path
import sys
import pytest
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _has_layout(html: str) -> bool:
    # A simple heuristic: our Layout renders a main element with id="main-content"
    return "<main id=\"main-content\"" in html


@pytest.mark.anyio
async def test_login_get_uses_form_components(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    # Check layout wrapper
    assert _has_layout(body), "Expected Layout wrapper for SSR page"
    # Check form structure and fields
    assert "class=\"form-field" in body, "FormField wrapper missing"
    assert "class=\"form-label" in body, "Form label missing"
    # Be permissive about attribute order/quoting; just ensure email+password fields exist
    assert 'name="email"' in body and 'type="email"' in body
    assert 'name="password"' in body and 'type="password"' in body
    assert "name=\"csrf_token\"" in body
    assert "btn btn-primary" in body, "Submit button style missing"


@pytest.mark.anyio
async def test_register_get_uses_form_components(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/register?login_hint=student%40example.com", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert _has_layout(body)
    assert "class=\"form-field" in body
    # Name field is optional but we include it in the UI
    assert 'name="display_name"' in body
    assert 'name="email"' in body and 'type="email"' in body
    assert 'name="password"' in body and 'type="password"' in body
    assert "name=\"csrf_token\"" in body
    assert "btn btn-primary" in body


@pytest.mark.anyio
async def test_forgot_get_uses_form_components(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/forgot?login_hint=student%40example.com", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert _has_layout(body)
    assert "class=\"form-field" in body
    assert 'name="email"' in body and 'type="email"' in body
    assert "name=\"csrf_token\"" in body
    assert "btn btn-primary" in body
