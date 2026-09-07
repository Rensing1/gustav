"""App isolation, privacy and scheduling for the concern-box HTTP boundary."""

from __future__ import annotations

import asyncio
import importlib
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.web.concern_box_providers import ConcernBoxProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE_ID = str(uuid4())
ENTRY_ID = str(uuid4())


class RepositoryStub:
    def __init__(self, label: str):
        self.label = label
        self.writes = []

    def list_courses_for_student(self, *, student_id, limit, offset):
        return [{"id": COURSE_ID, "title": self.label}]

    def student_has_course(self, course_id, student_sub):
        return course_id == COURSE_ID

    def create_concern_box_entry(self, **payload):
        self.writes.append(payload)
        return {"id": ENTRY_ID, "created_at": "2026-09-07T00:00:00+00:00"}

    def list_concern_box_entries_for_teacher(self, owner_sub, scope):
        return [
            {
                "id": ENTRY_ID,
                "message_text": self.label,
                "anonymous": True,
                "student_sub": "anonymous-sub",
            },
            {
                "id": ENTRY_ID,
                "message_text": self.label,
                "anonymous": False,
                "student_sub": "named-sub",
            },
        ]

    def archive_concern_box_entry_owned(self, entry_id, owner_sub):
        self.writes.append(("archive", entry_id, owner_sub))
        return True

    def restore_concern_box_entry_owned(self, entry_id, owner_sub):
        self.writes.append(("restore", entry_id, owner_sub))
        return True


def client_for(repo, *, role="student", names=lambda subs: {}):
    app = create_app(
        concern_box_providers=ConcernBoxProviders(repository=lambda: repo, resolve_names=names),
        access_token_verifier=lambda token, cfg: {
            "sub": "caller",
            "realm_access": {"roles": [role]},
        },
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt", "Origin": "http://test"},
    )


async def test_two_apps_keep_courses_and_mutations_isolated():
    first, second = RepositoryStub("First"), RepositoryStub("Second")
    async with client_for(first) as a, client_for(second) as b:
        for client, label in ((a, "First"), (b, "Second"), (a, "First")):
            response = await client.get("/api/learning/views/concern-box")
            assert response.status_code == 200
            assert response.json()["courses"] == [{"id": COURSE_ID, "title": label}]
        assert (
            await a.post(
                "/api/learning/concern-box/entries",
                json={"course_id": COURSE_ID, "message_text": "Hello"},
            )
        ).status_code == 201
    assert len(first.writes) == 1 and second.writes == []
    async with client_for(second, role="teacher") as b:
        for action in ("archive", "restore"):
            assert (
                await b.post(f"/api/teaching/concern-box/entries/{ENTRY_ID}/{action}")
            ).status_code == 204
    assert second.writes == [("archive", ENTRY_ID, "caller"), ("restore", ENTRY_ID, "caller")]
    assert len(first.writes) == 1


async def test_inbox_uses_only_own_name_provider_and_never_resolves_anonymous_subjects():
    calls = []

    def names(subs):
        calls.append(subs)
        return {"named-sub": "Named learner"}

    async with (
        client_for(RepositoryStub("A"), role="teacher", names=names) as a,
        client_for(RepositoryStub("B"), role="teacher") as b,
    ):
        for client, name in ((a, "Named learner"), (b, "Unbekannt"), (a, "Named learner")):
            response = await client.get("/api/teaching/views/concern-box")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "private, no-store"
            entries = response.json()["entries"]
            assert entries[0]["student_name"] is None
            assert entries[1]["student_name"] == name
            assert all("student_sub" not in entry for entry in entries)
    assert calls == [["named-sub"], ["named-sub"]]


async def test_waiting_repository_does_not_block_shell_requests():
    started, release = threading.Event(), threading.Event()

    class WaitingRepository(RepositoryStub):
        def list_courses_for_student(self, **kwargs):
            started.set()
            assert release.wait(5), "repository blocked the event loop"
            return super().list_courses_for_student(**kwargs)

    async with client_for(WaitingRepository("Waiting")) as client:
        pending = asyncio.create_task(client.get("/api/learning/views/concern-box"))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert (
                await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            ).status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 200


@pytest.mark.parametrize(
    "method,path,role,payload",
    [
        ("GET", "/api/learning/views/concern-box", "teacher", None),
        (
            "POST",
            "/api/learning/concern-box/entries",
            "teacher",
            {"course_id": COURSE_ID, "message_text": "Hello"},
        ),
        ("GET", "/api/teaching/views/concern-box", "student", None),
        ("POST", f"/api/teaching/concern-box/entries/{ENTRY_ID}/archive", "student", None),
        ("POST", f"/api/teaching/concern-box/entries/{ENTRY_ID}/restore", "student", None),
    ],
)
async def test_wrong_role_or_missing_auth_never_accesses_repository(method, path, role, payload):
    class ForbiddenRepository:
        def __getattr__(self, name):
            pytest.fail("unauthorized repository access")

    async with client_for(ForbiddenRepository(), role=role) as client:
        assert (await client.request(method, path, json=payload)).status_code == 403
        client.headers.pop("Authorization")
        assert (await client.request(method, path, json=payload)).status_code == 401


@pytest.mark.parametrize("action", ["create", "archive", "restore"])
async def test_cross_origin_mutations_do_not_access_repository(action):
    class ForbiddenRepository:
        def __getattr__(self, name):
            pytest.fail("cross-origin repository access")

    role = "student" if action == "create" else "teacher"
    path = (
        "/api/learning/concern-box/entries"
        if action == "create"
        else f"/api/teaching/concern-box/entries/{ENTRY_ID}/{action}"
    )
    payload = {"course_id": COURSE_ID, "message_text": "Hello"} if action == "create" else None
    async with client_for(ForbiddenRepository(), role=role) as client:
        response = await client.post(
            path, json=payload, headers={"Origin": "https://foreign.example"}
        )
        assert response.status_code == 403


def test_production_repository_is_lazy_app_scoped_and_retryable(monkeypatch):
    wiring = importlib.import_module("backend.web.concern_box_providers")
    attempts = []

    def construct():
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("unavailable")
        return RepositoryStub("DB")

    monkeypatch.setattr(wiring, "DBTeachingRepo", construct)
    first, second = wiring.create_concern_box_providers(), wiring.create_concern_box_providers()
    assert attempts == []
    with pytest.raises(wiring.TeachingRepositoryUnavailable):
        first.repository()
    one = first.repository()
    assert first.repository() is one
    assert second.repository() is not one
    assert len(attempts) == 3


@pytest.mark.parametrize("entries", [[], [{"anonymous": True, "student_sub": "hidden"}]])
def test_anonymous_or_empty_inbox_never_calls_directory(entries):
    from backend.teaching.services.concern_box import ConcernBoxService

    class AnonymousRepository(RepositoryStub):
        def list_concern_box_entries_for_teacher(self, owner_sub, scope):
            assert owner_sub == "owner" and scope == "open"
            return entries

    def forbidden_names(subs):
        pytest.fail("anonymous inbox accessed the directory")

    view = ConcernBoxService(AnonymousRepository("A"), forbidden_names).inbox("owner", "unknown")
    assert view["active_scope"] == "open"
    assert all(
        item["student_name"] is None and "student_sub" not in item for item in view["entries"]
    )


async def test_atomic_membership_denial_remains_forbidden():
    class RevokedRepository(RepositoryStub):
        def create_concern_box_entry(self, **payload):
            # Membership can disappear between the precheck and atomic insert.
            return None

    async with client_for(RevokedRepository("Revoked")) as client:
        response = await client.post(
            "/api/learning/concern-box/entries",
            json={"course_id": COURSE_ID, "message_text": "Hello"},
        )
        assert response.status_code == 403


async def test_unavailable_repository_returns_private_service_unavailable(monkeypatch):
    wiring = importlib.import_module("backend.web.concern_box_providers")

    def unavailable():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(wiring, "DBTeachingRepo", unavailable)
    app = create_app(
        access_token_verifier=lambda token, cfg: {
            "sub": "caller",
            "realm_access": {"roles": ["teacher"]},
        }
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt"},
    ) as client:
        response = await client.get("/api/teaching/views/concern-box")
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "database unavailable" not in response.text


def test_concern_box_router_owns_all_paths_without_dynamic_facades():
    routes = importlib.import_module("backend.web.routes.app_concern_box_routes")
    facade = importlib.import_module("backend.web.routes.app")
    assert len(routes.app_concern_box_router.routes) == 5
    for route in routes.app_concern_box_router.routes:
        assert route.endpoint.__module__ == routes.__name__
        assert not hasattr(facade, route.endpoint.__name__)
    source = Path(routes.__file__).read_text()
    for forbidden in (
        "sys.modules",
        "_app_module",
        "__globals__",
        "teaching_routes",
        "from backend.web.routes.app import",
    ):
        assert forbidden not in source
    service = importlib.import_module("backend.teaching.services.concern_box")
    source = Path(service.__file__).read_text()
    assert "backend.web" not in source and "fastapi" not in source
