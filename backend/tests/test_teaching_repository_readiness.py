"""Regression tests for fail-closed Teaching database readiness.

Why:
    A temporary database outage must never switch the production web process
    to volatile in-memory persistence. The process must report unavailability
    and retry repository construction after PostgreSQL becomes reachable.
"""

from __future__ import annotations

import importlib

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from backend.web.runtime_errors import (
    TeachingRepositoryUnavailable,
    install_runtime_error_handlers,
)


teaching = importlib.import_module("backend.web.routes.teaching")
basic_pages = importlib.import_module("backend.web.routes.basic_pages")


def test_default_repo_failure_is_not_replaced_or_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """The next request must retry after an initial PostgreSQL outage."""

    persistent_repo = object()
    attempts = 0

    def build_repo() -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TeachingRepositoryUnavailable()
        return persistent_repo

    monkeypatch.setattr(teaching, "_REPO", None)
    monkeypatch.setattr(teaching, "REPO", None)
    monkeypatch.setattr(teaching, "_build_default_repo", build_repo)
    # Other full-suite tests intentionally reload the Teaching route module.
    # Pin this isolated regression to the module object patched above.
    monkeypatch.setattr(teaching, "_current_teaching_module", lambda: teaching)

    with pytest.raises(TeachingRepositoryUnavailable):
        teaching._get_repo()

    assert teaching._REPO is None
    assert teaching.REPO is None
    assert teaching._get_repo() is persistent_repo
    assert attempts == 2


def test_default_repo_never_implicitly_builds_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing database adapter is a visible runtime error, not a mode switch."""

    monkeypatch.setattr(teaching, "DBTeachingRepo", None)
    monkeypatch.setattr(teaching, "_DB_REPO_IMPORT_ERROR", RuntimeError("driver unavailable"))

    with pytest.raises(TeachingRepositoryUnavailable):
        teaching._build_default_repo()


@pytest.mark.anyio
async def test_health_is_unhealthy_without_database_and_recovers_on_next_request() -> None:
    """Readiness retries in the same process and does not disclose DB details."""

    attempts = 0

    class ReadyRepo:
        def check_readiness(self) -> None:
            return None

    def repo_provider() -> ReadyRepo:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TeachingRepositoryUnavailable()
        return ReadyRepo()

    app = FastAPI()
    install_runtime_error_handlers(app)
    app.include_router(
        basic_pages.create_basic_pages_router(
            lambda *_args, **_kwargs: None,
            repo_provider=repo_provider,
        )
    )

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unavailable = await client.get("/health")
        recovered = await client.get("/health")

    assert unavailable.status_code == 503
    assert unavailable.json() == {"status": "unhealthy"}
    assert unavailable.headers["Cache-Control"] == "private, no-store"
    assert recovered.status_code == 200
    assert recovered.json() == {"status": "healthy"}
    assert attempts == 2


@pytest.mark.anyio
async def test_repository_unavailable_handler_returns_contract_error() -> None:
    """Teaching routes expose a stable private 503 response."""

    app = FastAPI()
    install_runtime_error_handlers(app)

    @app.get("/fails")
    async def fail() -> None:
        raise TeachingRepositoryUnavailable("secret database host")

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/fails")

    assert response.status_code == 503
    assert response.json() == {
        "error": "service_unavailable",
        "detail": "teaching_repository_unavailable",
    }
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "secret database host" not in response.text
