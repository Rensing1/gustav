"""Course read providers must remain isolated across independently wired apps."""

from __future__ import annotations

import asyncio
import importlib
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.web.learning_course_providers import LearningCourseProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE_ID = str(uuid4())
HOME = "/api/learning/views/learner-home"
COURSES = "/api/learning/courses"
UNITS = f"{COURSES}/{COURSE_ID}/units"


class RepositoryStub:
    def __init__(self, label):
        self.label = label
        self.calls = []

    def list_personal_courses(self, **kwargs):
        self.calls.append(kwargs)
        return [{"id": COURSE_ID, "title": self.label, "school_year_start": 2026}]

    def list_units_for_student_course(self, **kwargs):
        self.calls.append(kwargs)
        return [{"unit": {"id": "unit", "title": self.label}, "position": 1}]


def client_for(repo, *, role="student", factory=None):
    app = create_app(
        learning_course_providers=LearningCourseProviders(repository=factory or (lambda: repo)),
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


async def test_two_apps_keep_all_course_reads_and_home_projections_isolated():
    first, second = RepositoryStub("First"), RepositoryStub("Second")
    async with client_for(first) as a, client_for(second) as b:
        for client, label in ((a, "First"), (b, "Second"), (a, "First")):
            home = await client.get(HOME)
            assert home.status_code == 200
            assert home.headers["Cache-Control"] == "private, no-store"
            for scope in ("current", "past"):
                item = home.json()[f"{scope}_courses"][0]
                assert item == {
                    "id": COURSE_ID,
                    "title": label,
                    "school_year_start": 2026,
                    "href": f"/learning/courses/{COURSE_ID}"
                    + ("/archive" if scope == "past" else ""),
                }
                response = await client.get(COURSES, params={"scope": scope})
                assert response.json()[0]["title"] == label
            assert (await client.get(UNITS)).json()[0]["unit"]["title"] == label
    assert len(first.calls) == 10 and len(second.calls) == 5
    assert all(call["student_sub"] == "learner" for call in first.calls + second.calls)


@pytest.mark.parametrize("path", [HOME, COURSES, UNITS])
async def test_auth_and_role_guards_precede_repository_construction(path):
    def forbidden():
        pytest.fail("unauthorized dependency construction")

    async with client_for(None, role="teacher", factory=forbidden) as client:
        assert (await client.get(path)).status_code == 403
        client.headers.pop("Authorization")
        assert (await client.get(path)).status_code == 401


async def test_invalid_uuid_does_not_construct_repository():
    def forbidden():
        pytest.fail("invalid UUID reached repository")

    async with client_for(None, factory=forbidden) as client:
        response = await client.get(f"{COURSES}/invalid/units")
    assert response.status_code == 400
    assert response.json() == {"error": "bad_request", "detail": "invalid_uuid"}


async def test_bounds_scope_and_empty_home_preserve_existing_contract():
    class EmptyRepository(RepositoryStub):
        def list_personal_courses(self, **kwargs):
            super().list_personal_courses(**kwargs)
            return []

    repo = EmptyRepository("Empty")
    async with client_for(repo) as client:
        home = await client.get(HOME, params={"limit": 1000, "offset": -4})
        assert home.json()["current_courses"] == home.json()["past_courses"] == []
        assert (await client.get(COURSES, params={"scope": "invalid", "limit": -1})).json() == []
    assert [(call["scope"], call["limit"], call["offset"]) for call in repo.calls] == [
        ("current", 100, 0),
        ("past", 100, 0),
        ("current", 1, 0),
    ]


async def test_hidden_course_has_generic_private_not_found():
    class HiddenRepository(RepositoryStub):
        def list_units_for_student_course(self, **kwargs):
            raise LookupError("private membership details")

    async with client_for(HiddenRepository("Hidden")) as client:
        response = await client.get(UNITS)
    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}
    assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("path", [HOME, COURSES, UNITS])
async def test_waiting_repository_does_not_block_shell(path):
    started, release = threading.Event(), threading.Event()

    def repository():
        started.set()
        assert release.wait(5), "repository blocked event loop"
        return RepositoryStub("Waiting")

    async with client_for(None, factory=repository) as client:
        pending = asyncio.create_task(client.get(path))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert (
                await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            ).status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 200


def test_default_repository_is_lazy_retryable_and_app_owned(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_course_providers")
    attempts = []

    def construct():
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("unavailable")
        return RepositoryStub("DB")

    monkeypatch.setattr(wiring, "DBLearningRepo", construct)
    first, second = (
        wiring.create_learning_course_providers(),
        wiring.create_learning_course_providers(),
    )
    assert attempts == []
    with pytest.raises(RuntimeError):
        first.repository()
    assert first.repository() is first.repository()
    assert second.repository() is not first.repository()


def test_focused_routers_do_not_depend_on_dynamic_facades():
    for name in ("app_learner_view_routes", "learning_course_routes"):
        module = importlib.import_module(f"backend.web.routes.{name}")
        source = Path(module.__file__).read_text()
        for forbidden in (
            "_app_module",
            "__globals__",
            "sys.modules",
            "learning_routes",
            "importlib",
        ):
            assert forbidden not in source
    facade = importlib.import_module("backend.web.routes.app")
    assert not hasattr(facade, "get_learner_home")
    assert not hasattr(facade, "_list_learner_courses")
    learning = importlib.import_module("backend.web.routes.learning")
    assert not hasattr(learning, "list_my_courses")
    assert not hasattr(learning, "list_course_units")
