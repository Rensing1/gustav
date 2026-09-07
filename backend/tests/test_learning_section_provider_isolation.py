"""Explicit section reads preserve selections, pagination and material visibility."""

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

from backend.web.learning_section_providers import LearningSectionProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE, UNIT, SECTION, FILE, SIM = (str(uuid4()) for _ in range(5))
PATHS = [
    f"/api/learning/courses/{COURSE}/sections",
    f"/api/learning/courses/{COURSE}/units/{UNIT}/sections",
]


class Repository:
    def __init__(self, label="A"):
        self.label, self.calls = label, []
        self.rows = [
            {
                "section": {"id": SECTION, "unit_id": UNIT, "title": label},
                "materials": [{"id": FILE, "kind": "file"}, {"id": SIM, "kind": "simulation"}],
                "tasks": [{"instruction_md": label}],
            }
        ]

    def list_released_sections(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["student_sub"] == "learner"
        assert kwargs["course_id"] == COURSE
        if "unit_id" in kwargs:
            assert kwargs["unit_id"] == UNIT
        return [
            {
                **row,
                "materials": row["materials"] if kwargs["include_materials"] else [],
                "tasks": row["tasks"] if kwargs["include_tasks"] else [],
            }
            for row in self.rows
        ]

    list_released_sections_by_unit = list_released_sections


def client_for(repo=None, *, factory=None, role="student"):
    app = create_app(
        learning_section_providers=LearningSectionProviders(repository=factory or (lambda: repo)),
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


@pytest.mark.parametrize("path", PATHS)
async def test_sections_and_material_links_use_the_same_explicit_adapter(monkeypatch, path):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")
    observed = []

    def metadata(*, repo, student_sub, course_id, material_ids):
        assert (student_sub, course_id, material_ids) == ("learner", COURSE, [FILE, SIM])
        observed.append(repo)
        return {FILE: SimpleNamespace(kind="file"), SIM: SimpleNamespace(kind="simulation")}

    monkeypatch.setattr(helpers, "load_student_material_asset_metadata_batch", metadata)
    first, second = Repository("A"), Repository("B")
    original = deepcopy(first.rows)
    async with client_for(first) as a, client_for(second) as b:
        for client, label in [(a, "A"), (b, "B"), (a, "A")]:
            response = await client.get(path, params={"include": "materials,tasks"})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["vary"] == "Origin"
            row = response.json()[0]
            assert row["section"]["title"] == row["tasks"][0]["instruction_md"] == label
            assert (
                row["materials"][0]["file_url"]
                == f"/api/learning/courses/{COURSE}/materials/{FILE}/file?disposition=inline"
            )
            assert (
                row["materials"][1]["simulation_url"]
                == f"/api/learning/courses/{COURSE}/materials/{SIM}/simulation"
            )
    assert observed == [first, second, first]
    assert first.rows == original


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "include,flags",
    [
        (None, (False, False)),
        ("materials", (True, False)),
        ("tasks", (False, True)),
        ("tasks,materials", (True, True)),
        (" materials , materials ", (True, False)),
    ],
)
async def test_include_preserves_existing_defaults_and_tokens(path, include, flags):
    repo = Repository()
    repo.rows[0]["materials"] = [{"kind": "markdown", "body_md": "Text"}]
    async with client_for(repo) as client:
        response = await client.get(path, params={} if include is None else {"include": include})
        assert response.status_code == 200
        assert (repo.calls[0]["include_materials"], repo.calls[0]["include_tasks"]) == flags
        assert bool(response.json()[0]["materials"]) is flags[0]
        assert bool(response.json()[0]["tasks"]) is flags[1]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "limit,offset,expected", [(0, -4, (1, 0)), (1000, 8, (100, 8)), (50, 0, (50, 0))]
)
async def test_pagination_remains_owned_by_existing_use_cases(path, limit, offset, expected):
    repo = Repository()
    async with client_for(repo) as client:
        response = await client.get(path, params={"limit": limit, "offset": offset})
        assert response.status_code == 200
        assert (repo.calls[0]["limit"], repo.calls[0]["offset"]) == expected


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "case", ["uuid", "include_empty", "include_unknown", "include_trailing", "limit", "offset"]
)
async def test_invalid_inputs_precede_repository_construction(path, case):
    def forbidden():
        pytest.fail("invalid input reached repository")

    params = {
        "include_empty": {"include": ""},
        "include_unknown": {"include": "Tasks"},
        "include_trailing": {"include": "tasks,"},
        "limit": {"limit": "bad"},
        "offset": {"offset": "bad"},
    }.get(case, {})
    async with client_for(factory=forbidden) as client:
        response = await client.get(
            path.replace(COURSE, "invalid") if case == "uuid" else path, params=params
        )
        assert response.status_code == (422 if case in {"limit", "offset"} else 400)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("role", [None, "teacher", "admin"])
async def test_auth_and_roles_precede_dependencies(path, role):
    def forbidden():
        pytest.fail("unauthorized dependency access")

    async with client_for(factory=forbidden, role=role or "student") as client:
        if role is None:
            client.headers.clear()
        response = await client.get(path)
        assert response.status_code == (401 if role is None else 403)
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("error,status", [(PermissionError, 403), (LookupError, 404)])
async def test_repository_denials_precede_material_links(monkeypatch, path, error, status):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")
    monkeypatch.setattr(
        helpers,
        "load_student_material_asset_metadata_batch",
        lambda **kw: pytest.fail("denied read reached material metadata"),
    )

    def denied(**kwargs):
        raise error("private repository detail")

    repo = SimpleNamespace(list_released_sections=denied, list_released_sections_by_unit=denied)
    async with client_for(repo) as client:
        response = await client.get(path, params={"include": "materials"})
        assert response.status_code == status
        assert "private repository detail" not in response.text
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("path", PATHS)
async def test_failed_visibility_lookup_does_not_emit_links(monkeypatch, path):
    helpers = importlib.import_module("backend.web.routes.learning_material_files")

    def unavailable(**kwargs):
        raise RuntimeError("private metadata")

    monkeypatch.setattr(helpers, "load_student_material_asset_metadata_batch", unavailable)
    async with client_for(Repository()) as client:
        response = await client.get(path, params={"include": "materials"})
        assert response.status_code == 200
        assert all(
            item["file_url"] is None and item["simulation_url"] is None
            for item in response.json()[0]["materials"]
        )


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("phase", ["construction", "read"])
async def test_waiting_repository_does_not_block_shell(path, phase):
    started, release = threading.Event(), threading.Event()

    def factory():
        def wait():
            started.set()
            assert release.wait(5)

        repo = Repository()
        if phase == "construction":
            wait()
        else:

            def read(**kwargs):
                wait()
                return []

            repo.list_released_sections = read
            repo.list_released_sections_by_unit = read
        return repo

    async with client_for(factory=factory) as client:
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


def test_provider_is_lazy_and_retries_failed_initialization(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_section_providers")
    calls = []

    def build():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return Repository()

    monkeypatch.setattr(wiring, "DBLearningRepo", build)
    providers = wiring.create_learning_section_providers()
    assert not calls
    with pytest.raises(RuntimeError):
        providers.repository()
    assert providers.repository() is providers.repository()
    assert len(calls) == 2


def test_section_routes_and_material_helpers_have_no_legacy_facade():
    routes = importlib.import_module("backend.web.routes.learning_section_routes")
    assert not inspect.iscoroutinefunction(routes.list_sections)
    assert not inspect.iscoroutinefunction(routes.list_unit_sections)
    learning = importlib.import_module("backend.web.routes.learning")
    for name in (
        "list_sections",
        "list_unit_sections",
        "_attach_section_material_files",
        "_material_file_href",
        "_resolve_student_material_file_url",
        "_resolve_student_modular_material_file_url",
        "_parse_include",
    ):
        assert not hasattr(learning, name)
    helpers = importlib.import_module("backend.web.routes.learning_material_files")
    source = Path(helpers.__file__).read_text()
    assert "_get_repo" not in source and "_learning_module" not in source
    assert "resolve_student_material_file_url" not in source
    for name in ("attach_section_material_files", "load_visible_material_asset_metadata"):
        assert (
            inspect.signature(getattr(helpers, name)).parameters["repo"].default
            is inspect.Parameter.empty
        )
