"""Regression tests for fail-closed Teaching database readiness.

Why:
    A temporary database outage must never switch the production web process
    to volatile in-memory persistence. The process must report unavailability
    and retry repository construction after PostgreSQL becomes reachable.
"""

from __future__ import annotations

import asyncio
import importlib
import time
from types import SimpleNamespace

import httpx
import psycopg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from starlette.requests import Request

from backend.web.runtime_errors import (
    TeachingRepositoryUnavailable,
    install_runtime_error_handlers,
)


teaching = importlib.import_module("backend.web.routes.teaching")
basic_pages = importlib.import_module("backend.web.routes.basic_pages")
teaching_repo_db = importlib.import_module("backend.teaching.repo_db")
teaching_course_members = importlib.import_module("backend.web.routes.teaching_course_members")
teaching_guards = importlib.import_module("backend.web.routes.teaching_guards")
teaching_live = importlib.import_module("backend.web.routes.teaching_live")
teaching_units = importlib.import_module("backend.web.routes.teaching_units")


def _teacher_request(*, method: str = "GET", path: str = "/") -> Request:
    request = Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )
    request.state.user = {
        "sub": "teacher-sensitive-123456",
        "roles": ["teacher"],
    }
    return request


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


@pytest.mark.anyio
async def test_non_teaching_operational_error_is_not_mapped_to_teaching_503() -> None:
    """A global driver failure must not claim ownership by the Teaching context."""

    app = FastAPI()
    install_runtime_error_handlers(app)

    @app.get("/api/learning/fails")
    async def fail() -> None:
        raise psycopg.OperationalError("private learning database host")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/learning/fails")

    assert response.status_code == 500
    assert "teaching_repository_unavailable" not in response.text
    assert "private learning database host" not in response.text


def test_teaching_adapter_translates_operational_errors_at_its_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Teaching adapter owns translation from psycopg to its stable error."""

    repo = object.__new__(teaching_repo_db.DBTeachingRepo)
    repo._dsn = "postgresql://gustav_app:secret@database.invalid/postgres"

    def fail_connect(*_args, **_kwargs):
        raise psycopg.OperationalError("private teaching database host")

    monkeypatch.setattr(teaching_repo_db.psycopg, "connect", fail_connect)

    with pytest.raises(TeachingRepositoryUnavailable) as exc_info:
        repo.check_readiness()

    assert isinstance(exc_info.value.__cause__, psycopg.OperationalError)
    assert "private teaching database host" not in str(exc_info.value)


@pytest.mark.anyio
async def test_unit_list_propagates_repository_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A list route must not turn a database outage into a permission error."""

    class UnavailableRepo:
        def list_units_for_author(self, **_kwargs):
            raise TeachingRepositoryUnavailable()

    monkeypatch.setattr(teaching_units, "_get_repo", UnavailableRepo)

    with pytest.raises(TeachingRepositoryUnavailable):
        await teaching_units.list_units(_teacher_request(path="/api/teaching/units"))


def test_course_owner_guard_propagates_repository_unavailable() -> None:
    """Ownership checks must distinguish infrastructure failure from denial."""

    class UnavailableRepo(teaching_repo_db.DBTeachingRepo):
        def __init__(self) -> None:
            pass

        def course_exists_for_owner(self, *_args, **_kwargs):
            raise TeachingRepositoryUnavailable()

    with pytest.raises(TeachingRepositoryUnavailable):
        teaching_guards._guard_course_owner(
            "00000000-0000-0000-0000-000000000001",
            "teacher-sensitive-123456",
            repo_provider=UnavailableRepo,
        )


@pytest.mark.anyio
async def test_live_summary_propagates_repository_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live reads must not present an outage as a missing Course-Unit relation."""

    class UnavailableRepo:
        def list_course_modules_for_owner(self, *_args, **_kwargs):
            raise TeachingRepositoryUnavailable()

    monkeypatch.setattr(teaching_live, "_get_repo", UnavailableRepo)
    monkeypatch.setattr(teaching_live.teaching_guards, "_guard_course_owner", lambda *_args, **_kwargs: None)

    with pytest.raises(TeachingRepositoryUnavailable):
        await teaching_live.get_unit_live_summary(
            _teacher_request(path="/api/teaching/live"),
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        )


@pytest.mark.anyio
async def test_membership_write_propagates_repository_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teaching writes must not disguise an outage as unknown ownership."""

    class UnavailableRepo:
        def get_course(self, _course_id):
            return {"teacher_id": "teacher-sensitive-123456"}

        def add_member(self, *_args, **_kwargs):
            raise TeachingRepositoryUnavailable()

    monkeypatch.setattr(teaching_course_members, "_get_repo", UnavailableRepo)
    monkeypatch.setattr(teaching_course_members.teaching_guards, "_csrf_guard", lambda _request: None)
    monkeypatch.setattr(
        teaching_course_members,
        "_resp_non_owner_or_unknown",
        lambda *_args: object(),
    )

    with pytest.raises(TeachingRepositoryUnavailable):
        await teaching_course_members.add_member(
            _teacher_request(method="POST", path="/api/teaching/courses/course-1/members"),
            "course-1",
            SimpleNamespace(student_sub="student-1"),
        )


@pytest.mark.anyio
async def test_health_readiness_does_not_block_parallel_async_requests() -> None:
    """A slow synchronous DB probe must run outside the application event loop."""

    events: list[str] = []

    class SlowRepo:
        def check_readiness(self) -> None:
            events.append("health-start")
            time.sleep(0.2)
            events.append("health-end")

    app = FastAPI()
    app.include_router(
        basic_pages.create_basic_pages_router(
            lambda *_args, **_kwargs: None,
            repo_provider=SlowRepo,
        )
    )

    @app.get("/fast")
    async def fast() -> dict[str, str]:
        events.append("fast")
        return {"status": "fast"}

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_task = asyncio.create_task(client.get("/health"))
        await asyncio.sleep(0)
        fast_response = await client.get("/fast")
        health_response = await health_task

    assert fast_response.status_code == 200
    assert health_response.status_code == 200
    assert events.index("fast") < events.index("health-end")
