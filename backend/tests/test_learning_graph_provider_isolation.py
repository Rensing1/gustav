"""Student graph wiring, membership guards and unchanged error semantics."""

import asyncio
import importlib
import inspect
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.web.learning_graph_providers import LearningGraphProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE, UNIT = str(uuid4()), str(uuid4())
PATH = f"/api/learning/courses/{COURSE}/units/{UNIT}/modules/graph"


class GraphRepository:
    def __init__(self, label="Graph"):
        self.calls = []
        self.rows = [{"unit": {"id": UNIT, "unit_type": "modular"}, "position": 1}]
        self.payload = {
            "unit": {"id": UNIT, "title": label, "unit_type": "modular"},
            "phases": [{"id": "phase", "title": "Start", "position": 1}],
            "modules": [
                {"id": "first", "status": "open", "tasks_done": 0, "tasks_total": 1},
                {"id": "last", "status": "locked", "tasks_done": 0, "tasks_total": 2},
            ],
            "edges": [{"from": "first", "to": "last"}],
        }

    def list_units_for_student_course(self, *, student_sub, course_id):
        assert (student_sub, course_id) == ("learner", COURSE)
        self.calls.append("units")
        return self.rows

    def get_modular_unit_graph(self, *, student_sub, course_id, unit_id):
        assert (student_sub, course_id, unit_id) == ("learner", COURSE, UNIT)
        self.calls.append("graph")
        return self.payload


def client_for(repo=None, *, role="student", factory=None):
    app = create_app(
        learning_graph_providers=LearningGraphProviders(repository=factory or (lambda: repo)),
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


def assert_private(response):
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "Origin" in response.headers["Vary"].split(", ")


async def test_graph_dependencies_are_isolated_and_preserve_the_repository_payload():
    first, second = GraphRepository("A"), GraphRepository("B")
    async with client_for(first) as a, client_for(second) as b:
        for client, repo in [(a, first), (b, second), (a, first)]:
            response = await client.get(PATH)
            assert response.status_code == 200
            assert response.json() == repo.payload
            assert_private(response)
    assert first.calls == ["units", "graph"] * 2
    assert second.calls == ["units", "graph"]


@pytest.mark.parametrize("role", ["teacher", "admin"])
async def test_auth_and_roles_precede_repository_construction(role):
    def forbidden():
        pytest.fail("unauthorized dependency construction")

    async with client_for(role=role, factory=forbidden) as client:
        denied = await client.get(PATH)
        assert denied.status_code == 403
        assert_private(denied)
        client.headers.clear()
        absent = await client.get(PATH)
        assert absent.status_code == 401
        assert_private(absent)


@pytest.mark.parametrize("path", [PATH.replace(COURSE, "bad"), PATH.replace(UNIT, "bad")])
async def test_invalid_ids_precede_repository_construction(path):
    def forbidden():
        pytest.fail("invalid UUID reached repository")

    async with client_for(factory=forbidden) as client:
        response = await client.get(path)
        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "detail": "invalid_uuid"}
        assert_private(response)


async def test_canonical_ids_and_malformed_listing_rows_preserve_lookup_behavior():
    repo = GraphRepository()
    repo.rows = [
        {"unit": None},
        {"unit": "bad"},
        {"unit": {"id": "bad"}},
        {"unit": {"id": UNIT.upper(), "unit_type": " Modular "}},
    ]
    async with client_for(repo) as client:
        response = await client.get(
            PATH.replace(COURSE, COURSE.upper()).replace(UNIT, UNIT.upper())
        )
        assert response.status_code == 200
        assert response.json() == repo.payload
        assert repo.calls == ["units", "graph"]


@pytest.mark.parametrize(
    "case", ["not_member", "unassigned", "missing_unit", "revoked_during_read"]
)
async def test_invisible_resources_have_indistinguishable_private_not_found(case):
    repo = GraphRepository()

    def hidden(**kwargs):
        raise LookupError("private membership information")

    if case == "not_member":
        repo.list_units_for_student_course = hidden
    elif case == "revoked_during_read":
        repo.get_modular_unit_graph = hidden
    elif case == "unassigned":
        repo.rows = [{"unit": {"id": str(uuid4()), "unit_type": "modular"}}]
    else:
        repo.rows = []
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}
        assert_private(response)
    assert "graph" not in repo.calls


@pytest.mark.parametrize("case", ["linear", "missing_type", "changed_type"])
async def test_non_modular_units_keep_invalid_unit_type(case):
    repo = GraphRepository()
    if case == "changed_type":

        def changed(**kwargs):
            raise ValueError("private adapter detail")

        repo.get_modular_unit_graph = changed
    else:
        repo.rows[0]["unit"]["unit_type"] = "linear" if case == "linear" else None
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "detail": "invalid_unit_type"}
        assert_private(response)
    assert "graph" not in repo.calls


@pytest.mark.parametrize("visible,status", [(True, 503), (False, 404)])
async def test_missing_graph_capability_is_checked_only_after_membership(visible, status):
    repo = GraphRepository()
    repo.get_modular_unit_graph = None
    if not visible:
        repo.rows = []
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == status
        assert response.json() == {"error": "service_unavailable" if visible else "not_found"}
        assert_private(response)


async def test_empty_graph_is_not_treated_as_missing_unit():
    repo = GraphRepository()
    repo.payload.update(phases=[], modules=[], edges=[])
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == 200
        assert response.json() == repo.payload


async def test_waiting_repository_does_not_block_shell():
    started, release = threading.Event(), threading.Event()

    def factory():
        started.set()
        assert release.wait(5)
        return GraphRepository()

    async with client_for(factory=factory) as client:
        pending = asyncio.create_task(client.get(PATH))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert (
                await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            ).status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 200


def test_provider_is_lazy_and_retries_failed_initialization(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_graph_providers")
    calls = []

    def construct():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return GraphRepository()

    monkeypatch.setattr(wiring, "DBLearningRepo", construct)
    providers = wiring.create_learning_graph_providers()
    assert not calls
    with pytest.raises(RuntimeError, match="unavailable"):
        providers.repository()
    assert providers.repository() is providers.repository()
    assert len(calls) == 2


def test_graph_use_case_and_route_have_no_global_facade_dependency():
    usecase = importlib.import_module("backend.learning.usecases.unit_graph")
    source = Path(usecase.__file__).read_text()
    assert "backend.web" not in source and "fastapi" not in source
    route = importlib.import_module("backend.web.routes.learning_graph_routes")
    source = Path(route.__file__).read_text()
    for forbidden in ("_get_repo", "__globals__", "from backend.web.routes.learning import"):
        assert forbidden not in source
    assert not inspect.iscoroutinefunction(route.get_modular_unit_graph)
    assert not hasattr(
        importlib.import_module("backend.web.routes.learning"), "get_modular_unit_graph"
    )
