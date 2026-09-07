"""Workspace dependencies, selection rules and fail-closed ownership."""

import asyncio
import importlib
import inspect
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.main import create_app
from backend.web.teacher_workspace_providers import TeacherWorkspaceProviders

pytestmark = pytest.mark.anyio("asyncio")
UNIT, PHASE, FIRST, LAST, SECTION, COURSE = (str(uuid4()) for _ in range(6))
PATH = f"/api/teaching/views/units/{UNIT}/workspace"


class WorkspaceRepository:
    def __init__(self, title="A", unit_type="modular", owned=True, exists=True):
        self.title, self.unit_type = title, unit_type
        self.owned, self.exists = owned, exists
        self.content_reads = []

    def unit_exists_for_author(self, unit_id, author_id):
        assert (unit_id, author_id) == (UNIT, "owner")
        return self.owned

    def unit_exists(self, unit_id):
        return self.exists

    def get_unit_for_author(self, unit_id, author_id):
        assert self.owned and author_id == "owner"
        return {"id": UNIT, "title": self.title, "unit_type": self.unit_type}

    def list_courses_for_teacher(self, *, teacher_id, limit, offset):
        assert (teacher_id, limit, offset) == ("owner", 200, 0)
        return [{"id": COURSE, "title": "Kurs"}]

    def list_course_units_for_owner(self, course_id, owner_sub):
        assert (course_id, owner_sub) == (COURSE, "owner")
        return [{"id": UNIT}]

    def list_sections_for_author(self, unit_id, author_id):
        return [{"id": SECTION, "title": self.title, "position": 1}]

    def list_unit_phases_for_author(self, unit_id, author_id):
        return [{"id": PHASE, "title": "Phase", "position": 1}]

    def list_unit_modules_for_author(self, *, unit_id, author_id):
        return [
            {
                "id": node,
                "title": title,
                "phase_id": PHASE,
                "section_id": SECTION,
                "position_in_phase": pos,
                "module_kind": kind,
            }
            for node, title, pos, kind in [
                (FIRST, "Start", 1, "learning"),
                (LAST, "Üben", 2, "practice"),
            ]
        ]

    def list_unit_module_edges_for_author(self, *, unit_id, author_id):
        return [{"from_module_id": FIRST, "to_module_id": LAST, "private": "hidden"}]

    def list_materials_for_section_owned(self, unit_id, section_id, author_id):
        assert (unit_id, section_id, author_id) == (UNIT, SECTION, "owner")
        self.content_reads.append(section_id)
        return [{"storage_key": "private/key"}]

    def list_tasks_for_section_owned(self, unit_id, section_id, author_id):
        assert (unit_id, section_id, author_id) == (UNIT, SECTION, "owner")
        self.content_reads.append(section_id)
        return [{"model_solution_md": "Teacher only"}]


def client_for(repo=None, role="teacher", factory=None):
    app = create_app(
        teacher_workspace_providers=TeacherWorkspaceProviders(repository=factory or (lambda: repo)),
        access_token_verifier=lambda token, cfg: {
            "sub": "owner",
            "realm_access": {"roles": [role]},
        },
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt"},
    )


async def test_workspace_dependencies_are_isolated_and_project_only_graph_metadata():
    async with (
        client_for(WorkspaceRepository("A")) as first,
        client_for(WorkspaceRepository("B", "linear"), role="admin") as second,
    ):
        for client, title, kind in [
            (first, "A", "modular"),
            (second, "B", "linear"),
            (first, "A", "modular"),
        ]:
            response = await client.get(PATH)
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "private, no-store"
            body = response.json()
            assert body["unit"]["title"] == title
            assert body["graph"]["kind"] == kind
            assert body["counts"]["courses_count"] == 1
            nodes = (
                body["graph"]["phases"][0]["modules"]
                if kind == "modular"
                else body["graph"]["nodes"]
            )
            assert all(node["materials_count"] == node["tasks_count"] == 1 for node in nodes)
            assert "private/key" not in response.text and "Teacher only" not in response.text
            if kind == "modular":
                assert body["graph"]["edges"] == [{"from": FIRST, "to": LAST}]
                assert body["selection"]["module"]["id"] == FIRST
                assert nodes[-1]["module_kind"] == "practice"


@pytest.mark.parametrize(
    "params,kind",
    [
        ({"phase_id": PHASE}, "phase"),
        ({"module_id": LAST, "phase_id": PHASE}, "module"),
        ({"module_id": LAST, "edge_from_module_id": FIRST, "edge_to_module_id": LAST}, "edge"),
        ({"edge_from_module_id": FIRST}, "none"),
        ({"module_id": str(uuid4())}, "none"),
    ],
)
async def test_selection_priority_and_unknown_selection(params, kind):
    async with client_for(WorkspaceRepository()) as client:
        response = await client.get(PATH, params=params)
        assert response.status_code == 200
        assert response.json()["selection"]["kind"] == kind


@pytest.mark.parametrize(
    "unit_type,parameter",
    [
        ("linear", "section_id"),
        ("modular", "phase_id"),
        ("modular", "module_id"),
        ("modular", "edge_from_module_id"),
        ("modular", "edge_to_module_id"),
    ],
)
async def test_invalid_selection_is_private_and_reads_no_content(unit_type, parameter):
    repo = WorkspaceRepository(unit_type=unit_type)
    async with client_for(repo) as client:
        response = await client.get(PATH, params={parameter: "bad"})
        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "detail": f"invalid_{parameter}"}
        assert response.headers["Cache-Control"] == "private, no-store"
        assert not repo.content_reads


@pytest.mark.parametrize(
    "owned,exists,status", [(False, True, 403), (False, False, 404), (False, None, 403)]
)
async def test_ownership_precedes_content_reads(owned, exists, status):
    repo = WorkspaceRepository(owned=owned, exists=exists)
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == status
        assert response.headers["Cache-Control"] == "private, no-store"
        assert not repo.content_reads


@pytest.mark.parametrize(
    "case,status", [("guard_error", 403), ("vanished_unit", 404), ("missing_adapter", 503)]
)
async def test_lookup_failures_never_read_content(case, status):
    repo = WorkspaceRepository()
    if case == "guard_error":

        def broken(*args):
            raise RuntimeError("internal failure")

        repo.unit_exists_for_author = broken
    elif case == "vanished_unit":
        repo.get_unit_for_author = lambda *args: None
    else:
        repo.list_unit_phases_for_author = None
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == status
        assert response.headers["Cache-Control"] == "private, no-store"
        assert not repo.content_reads


async def test_auth_roles_and_invalid_unit_precede_repository_construction():
    def forbidden():
        pytest.fail("repository must not be accessed")

    async with client_for(factory=forbidden) as client:
        response = await client.get(PATH.replace(UNIT, "bad"))
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_unit_id"
        client.headers.clear()
        assert (await client.get(PATH)).status_code == 401
    async with client_for(role="student", factory=forbidden) as client:
        assert (await client.get(PATH)).status_code == 403


async def test_unavailable_repository_returns_private_503():
    def unavailable():
        raise TeachingRepositoryUnavailable()

    async with client_for(factory=unavailable) as client:
        response = await client.get(PATH)
        assert response.status_code == 503
        assert response.json() == {
            "error": "service_unavailable",
            "detail": "teaching_repository_unavailable",
        }
        assert response.headers["Cache-Control"] == "private, no-store"


async def test_waiting_repository_does_not_block_shell():
    started, release = threading.Event(), threading.Event()

    def factory():
        started.set()
        assert release.wait(5)
        return WorkspaceRepository()

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
    wiring = importlib.import_module("backend.web.teacher_workspace_providers")
    calls = []

    def construct():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return WorkspaceRepository()

    monkeypatch.setattr(wiring, "DBTeachingRepo", construct)
    providers = wiring.create_teacher_workspace_providers()
    assert not calls
    with pytest.raises(TeachingRepositoryUnavailable):
        providers.repository()
    assert providers.repository() is providers.repository()
    assert len(calls) == 2


def test_service_is_framework_independent_and_handler_has_no_global_provider():
    service = importlib.import_module("backend.teaching.services.unit_workspace")
    source = Path(service.__file__).read_text()
    assert "backend.web" not in source and "fastapi" not in source
    route = importlib.import_module("backend.web.routes.app_teacher_unit_routes")
    source = inspect.getsource(route.get_teacher_unit_workspace)
    assert not inspect.iscoroutinefunction(route.get_teacher_unit_workspace)
    for forbidden in ("teaching_routes", "teaching_guards", "__globals__"):
        assert forbidden not in source
