"""Explicit H5P authorization preserves the contract without global route repair."""

import asyncio
import importlib
import inspect
import threading
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.routing import APIRoute

from backend.web.learning_h5p_providers import LearningH5PProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE = str(uuid4())
PATH = f"/api/learning/courses/{COURSE}/h5p/contents/42/access"


def client_for(factory, *, role="student"):
    app = create_app(
        learning_h5p_providers=LearningH5PProviders(repository=factory),
        access_token_verifier=lambda token, cfg: {
            "sub": "learner",
            "realm_access": {"roles": [role]},
        },
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt"},
    )


async def test_access_uses_only_the_explicit_repository():
    calls = []

    def repo(label, allowed):
        def check(**kwargs):
            calls.append((label, kwargs))
            return allowed

        return SimpleNamespace(is_h5p_content_released_for_student=check)

    async with client_for(lambda: repo("A", True)) as a, client_for(lambda: repo("B", False)) as b:
        for client, status in [(a, 204), (b, 404), (a, 204)]:
            response = await client.get(PATH)
            assert response.status_code == status
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["vary"] == "Origin"
            if status == 204:
                assert response.content == b""
            else:
                assert response.json() == {"error": "not_found"}
    assert calls == [
        (label, {"student_sub": "learner", "course_id": COURSE, "content_id": "42"})
        for label in ("A", "B", "A")
    ]


@pytest.mark.parametrize("role", [None, "teacher", "admin"])
async def test_unauthorized_requests_do_not_build_repository(role):
    def forbidden():
        pytest.fail("unauthorized request reached DB construction")

    async with client_for(forbidden, role=role or "student") as client:
        if role is None:
            client.headers.clear()
        response = await client.get(PATH)
        assert response.status_code == (401 if role is None else 403)
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("content_id", ["x", "-1", "+1", "1.0", "١", "１", " 1", "1\n"])
async def test_invalid_content_ids_are_rejected_before_repository(content_id):
    from urllib.parse import quote

    def forbidden():
        pytest.fail("invalid input reached DB construction")

    async with client_for(forbidden) as client:
        response = await client.get(PATH.replace("/42/", f"/{quote(content_id, safe='')}/"))
        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "detail": "invalid_content_id"}
        assert response.headers["cache-control"] == "private, no-store"


async def test_invalid_course_precedes_content_validation_and_repository():
    def forbidden():
        pytest.fail("invalid input reached DB construction")

    async with client_for(forbidden) as client:
        response = await client.get(PATH.replace(COURSE, "bad").replace("/42/", "/bad/"))
        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "detail": "invalid_uuid"}


@pytest.mark.parametrize("content_id", ["0", "00042", "9" * 100])
async def test_ascii_digit_ids_are_passed_through_without_new_normalization(content_id):
    observed = []

    def check(**kwargs):
        observed.append(kwargs)
        return False

    async with client_for(
        lambda: SimpleNamespace(is_h5p_content_released_for_student=check)
    ) as client:
        response = await client.get(PATH.replace("/42/", f"/{content_id}/"))
        assert response.status_code == 404
    assert observed[0]["content_id"] == content_id


@pytest.mark.parametrize("phase", ["construction", "read"])
async def test_blocking_h5p_check_keeps_shell_responsive(phase):
    started, release = threading.Event(), threading.Event()

    def wait():
        started.set()
        assert release.wait(5)

    def factory():
        if phase == "construction":
            wait()

        def check(**kwargs):
            if phase == "read":
                wait()
            return True

        return SimpleNamespace(is_h5p_content_released_for_student=check)

    async with client_for(factory) as client:
        pending = asyncio.create_task(client.get(PATH))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            response = await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            assert response.status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 204


def test_provider_is_lazy_and_retries_initialization(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_h5p_providers")
    calls = []
    repository = object()

    def build():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return repository

    monkeypatch.setattr(wiring, "DBLearningRepo", build)
    provider = wiring.create_learning_h5p_providers()
    assert not calls
    with pytest.raises(RuntimeError):
        provider.repository()
    assert provider.repository() is provider.repository() is repository
    assert len(calls) == 2


def test_no_learning_endpoint_needs_global_repository_repair():
    main = importlib.import_module("backend.web.main")
    learning = importlib.import_module("backend.web.routes.learning")
    routes = importlib.import_module("backend.web.routes.learning_h5p_routes")
    assert not inspect.iscoroutinefunction(routes.check_h5p_content_access)
    assert not hasattr(learning, "check_h5p_content_access")
    assert "route_globals" not in inspect.getsource(learning.set_repo)
    for route in main.app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/learning"):
            assert "_REPO" not in route.endpoint.__globals__, route.path
