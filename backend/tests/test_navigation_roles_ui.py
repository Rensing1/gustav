"""Contracts for retiring the remaining FastAPI shell pages."""

from __future__ import annotations

import importlib

import httpx
import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store


main = importlib.import_module("backend.web.main")

pytestmark = pytest.mark.anyio("asyncio")


def test_fastapi_shell_no_longer_registers_home_or_about_pages() -> None:
    """The product entry surface belongs to SvelteKit, not FastAPI HTML."""

    operations = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert ("/", "GET") not in operations
    assert ("/about", "GET") not in operations
    assert ("/health", "GET") in operations


@pytest.mark.anyio
async def test_fastapi_shell_home_and_about_are_not_product_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authenticated requests to removed shell pages should not render legacy HTML."""

    session_store = install_session_store(monkeypatch, main)
    session = session_store.create(sub="teacher-shell-retired", name="Teacher", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session.session_id)
        home = await client.get("/")
        about = await client.get("/about")

    assert home.status_code == 404
    assert about.status_code == 404


@pytest.mark.anyio
async def test_retired_product_route_still_returns_410(monkeypatch: pytest.MonkeyPatch) -> None:
    """Removing shell pages must not weaken existing retired-product responses."""

    session_store = install_session_store(monkeypatch, main)
    session = session_store.create(sub="teacher-retired-route", name="Teacher", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session.session_id)
        units = await client.get("/units")

    assert units.status_code == 410
    assert "legacy route retired" in units.text.lower()
