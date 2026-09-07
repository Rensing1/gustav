"""Editor ownership, explicit dependencies and unchanged task payloads."""

import asyncio
import importlib
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.main import create_app
from backend.web.teacher_editor_providers import TeacherEditorProviders

pytestmark = pytest.mark.anyio("asyncio")
UNIT, NODE, SECTION = (str(uuid4()) for _ in range(3))
PATH = f"/api/teaching/views/units/{UNIT}/nodes/{NODE}/editor"


class EditorRepository:
    def __init__(self, title="A", unit_type="linear", owned=True, exists=True):
        self.title, self.unit_type = title, unit_type
        self.owned, self.exists = owned, exists
        self.content_reads = []

    def unit_exists_for_author(self, unit_id, author_id):
        assert unit_id == UNIT and author_id == "owner"
        return self.owned

    def unit_exists(self, unit_id):
        return self.exists

    def get_unit_for_author(self, unit_id, author_id):
        assert self.owned and author_id == "owner"
        return {"id": UNIT, "title": self.title, "unit_type": self.unit_type, "summary": None}

    def list_sections_for_author(self, unit_id, author_id):
        return [{"id": NODE, "title": self.title}]

    def get_unit_module_for_author(self, *, unit_id, module_id, author_id):
        assert (unit_id, module_id, author_id) == (UNIT, NODE, "owner")
        return {
            "title": self.title,
            "section_id": SECTION,
            "module_kind": "practice",
            "required_prereq_count": 2,
        }

    def list_materials_for_section_owned(self, unit_id, section_id, author_id):
        assert (unit_id, author_id) == (UNIT, "owner")
        self.content_reads.append(section_id)
        return [
            {"id": "material", "title": self.title, "position": 1, "storage_key": "private/key"}
        ]

    def list_tasks_for_section_owned(self, unit_id, section_id, author_id):
        assert (unit_id, author_id) == (UNIT, "owner")
        self.content_reads.append(section_id)
        return [
            {
                "id": "task",
                "kind": "h5p",
                "h5p_content_id": "content-1",
                "h5p_display_options": {"frame": True},
                "model_solution_md": "Teacher only",
            }
        ]


def client_for(repo=None, role="teacher", factory=None):
    app = create_app(
        teacher_editor_providers=TeacherEditorProviders(repository=factory or (lambda: repo)),
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


async def test_editor_dependencies_are_isolated_and_modular_content_uses_backing_section():
    linear, modular = EditorRepository(), EditorRepository("B", "modular")
    async with client_for(linear) as first, client_for(modular, role="admin") as second:
        for client, title, kind in [
            (first, "A", "section"),
            (second, "B", "module"),
            (first, "A", "section"),
        ]:
            response = await client.get(PATH)
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "private, no-store"
            body = response.json()
            assert body["unit"]["title"] == body["node"]["title"] == title
            assert body["node"]["kind"] == kind
            assert "storage_key" not in body["materials"][0]
            assert body["tasks"][0]["h5p"] == {
                "content_id": "content-1",
                "display_options": {"frame": True},
            }
            assert "h5p_content_id" not in body["tasks"][0]
            assert body["tasks"][0]["model_solution_md"] == "Teacher only"
            if kind == "module":
                assert body["node"]["backing_section_id"] == SECTION
                assert body["settings"] == {
                    "kind": "module",
                    "module_kind": "practice",
                    "required_prereq_count": 2,
                }
    assert linear.content_reads == [NODE] * 4
    assert modular.content_reads == [SECTION] * 2


@pytest.mark.parametrize(
    "owned,exists,status", [(False, True, 403), (False, False, 404), (False, None, 403)]
)
async def test_ownership_precedes_content_reads(owned, exists, status):
    repo = EditorRepository(owned=owned, exists=exists)
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == status
        assert response.headers["Cache-Control"] == "private, no-store"
        assert repo.content_reads == []


@pytest.mark.parametrize(
    "case,status",
    [
        ("guard_error", 403),
        ("vanished_unit", 404),
        ("absent_module", 404),
        ("missing_module_adapter", 503),
    ],
)
async def test_lookup_failures_never_read_content(case, status):
    repo = EditorRepository(unit_type="modular")
    if case == "guard_error":

        def broken(*args):
            raise RuntimeError("internal failure")

        repo.unit_exists_for_author = broken
    elif case == "vanished_unit":
        repo.get_unit_for_author = lambda *args: None
    elif case == "absent_module":
        repo.get_unit_module_for_author = lambda **kwargs: None
    else:
        repo.get_unit_module_for_author = None
    async with client_for(repo) as client:
        response = await client.get(PATH)
        assert response.status_code == status
        assert response.headers["Cache-Control"] == "private, no-store"
        assert repo.content_reads == []


async def test_auth_roles_and_invalid_ids_precede_repository_construction():
    def forbidden():
        pytest.fail("repository must not be accessed")

    async with client_for(factory=forbidden) as client:
        for path, detail in [
            (PATH.replace(UNIT, "bad"), "invalid_unit_id"),
            (PATH.replace(NODE, "bad"), "invalid_node_id"),
        ]:
            response = await client.get(path)
            assert response.status_code == 400
            assert response.json() == {"error": "bad_request", "detail": detail}
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
        return EditorRepository()

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
    wiring = importlib.import_module("backend.web.teacher_editor_providers")
    calls = []

    def construct():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return EditorRepository()

    monkeypatch.setattr(wiring, "DBTeachingRepo", construct)
    providers = wiring.create_teacher_editor_providers()
    assert not calls
    with pytest.raises(TeachingRepositoryUnavailable):
        providers.repository()
    assert providers.repository() is providers.repository()
    assert len(calls) == 2


def test_service_is_framework_independent_and_handler_has_no_facade():
    service = importlib.import_module("backend.teaching.services.node_editor")
    source = Path(service.__file__).read_text()
    assert "backend.web" not in source and "fastapi" not in source
    route = importlib.import_module("backend.web.routes.app_teacher_node_editor_routes")
    source = Path(route.__file__).read_text()
    for forbidden in (
        "teaching_routes",
        "teaching_guards",
        "app_teacher_unit_routes",
        "__globals__",
    ):
        assert forbidden not in source


@pytest.mark.parametrize(
    "kind", ["native", "visual", "scratch", "calliope", "filius", "dialog", "h5p"]
)
def test_task_normalization_preserves_existing_serializer_contract(kind):
    from backend.teaching.task_payload import serialize_task

    task = {
        "kind": kind,
        "criteria": None,
        "h5p_content_id": "42",
        "h5p_display_options": {},
        "dialog": {"partner_name": "Partner"},
    }
    normalized = serialize_task(task)
    serializers = importlib.import_module("backend.web.routes.teaching_serialization")
    assert serializers._serialize_task is serialize_task
    assert normalized["criteria"] == []
    assert "h5p_content_id" not in normalized
    assert "h5p_content_id" in task
    if kind in ("visual", "scratch", "calliope", "filius"):
        assert normalized[kind] == {}
    if kind == "dialog":
        assert normalized[kind] == {"partner_name": "Partner"}
