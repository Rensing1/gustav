"""Module content dependencies, selections and fail-closed material links."""

import asyncio
import importlib
import inspect
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from backend.web.learning_module_providers import LearningModuleProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE, UNIT, MODULE, FILE, SIMULATION = (str(uuid4()) for _ in range(5))
PATH = f"/api/learning/courses/{COURSE}/units/{UNIT}/modules/{MODULE}"


class ModuleRepository:
    def __init__(self, label="A"):
        self.label, self.calls = label, []
        self.rows = [{"unit": {"id": UNIT, "unit_type": "modular"}}]
        self.payload = {
            "module": {"id": MODULE, "title": label},
            "materials": [{"id": FILE, "kind": "file"}, {"id": SIMULATION, "kind": "simulation"}],
            "tasks": [{"id": "task", "instruction_md": label, "kind": "native", "criteria": []}],
        }

    def list_units_for_student_course(self, *, student_sub, course_id):
        assert (student_sub, course_id) == ("learner", COURSE)
        self.calls.append("units")
        return self.rows

    def get_modular_module_content(self, **kwargs):
        assert (
            kwargs["student_sub"],
            kwargs["course_id"],
            kwargs["unit_id"],
            kwargs["module_id"],
        ) == ("learner", COURSE, UNIT, MODULE)
        self.calls.append((kwargs["include_materials"], kwargs["include_tasks"]))
        return {
            **self.payload,
            "materials": self.payload["materials"] if kwargs["include_materials"] else [],
            "tasks": self.payload["tasks"] if kwargs["include_tasks"] else [],
        }


def client_for(repo=None, role="student", factory=None):
    app = create_app(
        learning_module_providers=LearningModuleProviders(repository=factory or (lambda: repo)),
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
    assert "Origin" in response.headers["Vary"]


async def test_content_and_material_metadata_use_the_same_explicit_repository(monkeypatch):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")
    observed = []

    def metadata(*, repo, student_sub, course_id, material_ids):
        assert (student_sub, course_id, material_ids) == ("learner", COURSE, [FILE, SIMULATION])
        observed.append(repo)
        return {FILE: SimpleNamespace(kind="file"), SIMULATION: SimpleNamespace(kind="simulation")}

    monkeypatch.setattr(helpers, "load_student_material_asset_metadata_batch", metadata)
    first, second = ModuleRepository("A"), ModuleRepository("B")
    original = deepcopy(first.payload)
    async with client_for(first) as a, client_for(second) as b:
        for client, label in [(a, "A"), (b, "B"), (a, "A")]:
            response = await client.get(PATH)
            assert response.status_code == 200
            assert_private(response)
            body = response.json()
            assert body["module"]["title"] == body["tasks"][0]["instruction_md"] == label
            assert (
                body["materials"][0]["file_url"]
                == f"/api/learning/courses/{COURSE}/materials/{FILE}/file?disposition=inline"
            )
            assert body["materials"][0]["simulation_url"] is None
            assert (
                body["materials"][1]["simulation_url"]
                == f"/api/learning/courses/{COURSE}/materials/{SIMULATION}/simulation"
            )
            assert body["materials"][1]["file_url"] is None
    assert observed == [first, second, first]
    assert first.payload == original


@pytest.mark.parametrize(
    "include,flags",
    [
        (None, (True, True)),
        ("materials", (True, False)),
        ("tasks", (False, True)),
        ("tasks,materials", (True, True)),
        (" materials , materials ", (True, False)),
    ],
)
async def test_include_and_uppercase_ids_keep_existing_semantics(include, flags):
    repo = ModuleRepository()
    repo.payload["materials"] = [{"id": FILE, "kind": "markdown", "body_md": "Text"}]
    async with client_for(repo) as client:
        response = await client.get(
            PATH.replace(COURSE, COURSE.upper())
            .replace(UNIT, UNIT.upper())
            .replace(MODULE, MODULE.upper()),
            params={} if include is None else {"include": include},
        )
        assert response.status_code == 200
        assert repo.calls == ["units", flags]
        assert bool(response.json()["materials"]) is flags[0]
        assert bool(response.json()["tasks"]) is flags[1]


@pytest.mark.parametrize("include", ["", " ", "materials,", ",tasks", "Materials", "tasks,unknown"])
async def test_invalid_include_precedes_repository_construction(include):
    def forbidden():
        pytest.fail("invalid selection reached repository")

    async with client_for(factory=forbidden) as client:
        response = await client.get(PATH, params={"include": include})
        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "detail": "invalid_include"}
        assert_private(response)


@pytest.mark.parametrize("value", [COURSE, UNIT, MODULE])
async def test_invalid_uuid_precedes_repository_construction(value):
    def forbidden():
        pytest.fail("invalid UUID reached repository")

    async with client_for(factory=forbidden) as client:
        response = await client.get(PATH.replace(value, "bad"))
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_uuid"
        assert_private(response)


@pytest.mark.parametrize("role", ["teacher", "admin"])
async def test_roles_and_auth_precede_repository_construction(role):
    def forbidden():
        pytest.fail("unauthorized dependency construction")

    async with client_for(role=role, factory=forbidden) as client:
        response = await client.get(PATH)
        assert response.status_code == 403
        assert_private(response)
        client.headers.clear()
        response = await client.get(PATH)
        assert response.status_code == 401
        assert_private(response)


@pytest.mark.parametrize(
    "case,status",
    [
        ("not_member", 404),
        ("unassigned", 404),
        ("locked", 404),
        ("linear", 400),
        ("type_changed", 400),
        ("missing_adapter", 503),
    ],
)
async def test_rejections_never_resolve_material_links(monkeypatch, case, status):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")
    monkeypatch.setattr(
        helpers,
        "load_student_material_asset_metadata_batch",
        lambda **kw: pytest.fail("denied content reached assets"),
    )
    repo = ModuleRepository()

    def hidden(**kwargs):
        raise LookupError("private detail")

    def changed(**kwargs):
        raise ValueError("private detail")

    if case == "not_member":
        repo.list_units_for_student_course = hidden
    elif case == "unassigned":
        repo.rows = []
    elif case == "locked":
        repo.get_modular_module_content = hidden
    elif case == "linear":
        repo.rows[0]["unit"]["unit_type"] = "linear"
    elif case == "type_changed":
        repo.get_modular_module_content = changed
    else:
        repo.get_modular_module_content = None
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == status
        assert "private detail" not in response.text
        assert_private(response)


@pytest.mark.parametrize("case", ["unavailable", "wrong_kind", "hidden"])
async def test_unconfirmed_asset_visibility_never_produces_links(monkeypatch, case):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")

    def metadata(**kwargs):
        if case == "unavailable":
            raise RuntimeError("private storage metadata")
        if case == "wrong_kind":
            return {
                FILE: SimpleNamespace(kind="simulation"),
                SIMULATION: SimpleNamespace(kind="file"),
            }
        return {}

    monkeypatch.setattr(helpers, "load_student_material_asset_metadata_batch", metadata)
    async with client_for(ModuleRepository()) as client:
        response = await client.get(PATH)
        assert response.status_code == 200
        assert all(
            item["file_url"] is None and item["simulation_url"] is None
            for item in response.json()["materials"]
        )


async def test_invalid_material_ids_never_reach_metadata_lookup(monkeypatch):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")
    monkeypatch.setattr(
        helpers,
        "load_student_material_asset_metadata_batch",
        lambda **kwargs: pytest.fail("invalid material IDs reached metadata lookup"),
    )
    repo = ModuleRepository()
    repo.payload["materials"] = [
        {"id": "invalid", "kind": "file"},
        {"kind": "simulation"},
    ]
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == 200
        assert all(
            item["file_url"] is None and item["simulation_url"] is None
            for item in response.json()["materials"]
        )


async def test_waiting_repository_does_not_block_shell():
    started, release = threading.Event(), threading.Event()

    def factory():
        started.set()
        assert release.wait(5)
        repo = ModuleRepository()
        repo.payload["materials"] = []
        return repo

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
    wiring = importlib.import_module("backend.web.learning_module_providers")
    calls = []

    def construct():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return ModuleRepository()

    monkeypatch.setattr(wiring, "DBLearningRepo", construct)
    providers = wiring.create_learning_module_providers()
    assert not calls
    with pytest.raises(RuntimeError):
        providers.repository()
    assert providers.repository() is providers.repository()
    assert len(calls) == 2


def test_module_use_case_is_independent_and_route_has_no_facade():
    for module_name in ("module_content", "modular_unit_access"):
        module = importlib.import_module(f"backend.learning.usecases.{module_name}")
        source = Path(module.__file__).read_text()
        assert "backend.web" not in source and "fastapi" not in source
    route = importlib.import_module("backend.web.routes.learning_module_routes")
    assert not inspect.iscoroutinefunction(route.get_modular_unit_module_content)
    source = Path(route.__file__).read_text()
    assert "_get_repo" not in source and "__globals__" not in source
    learning = importlib.import_module("backend.web.routes.learning")
    assert not hasattr(learning, "get_modular_unit_module_content")
    assert not hasattr(learning, "_attach_modular_material_files")
