"""Dialog calls use explicit request-scoped services and bounded synchronous execution."""

import asyncio
import threading
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE, TASK, SESSION, TURN = (str(uuid4()) for _ in range(4))
BASE = f"/api/learning/courses/{COURSE}/tasks/{TASK}/dialog-sessions"
OPERATIONS = [
    ("post", "", "start", {}, 201),
    ("get", f"/{SESSION}", "get", None, 200),
    ("post", f"/{SESSION}/turns", "send_turn", {"student_message_md": "Antwort"}, 200),
    ("post", f"/{SESSION}/turns/{TURN}/retry", "retry_turn", {}, 200),
    ("post", f"/{SESSION}/complete", "complete", {"closing_answer_md": "Fazit"}, 200),
    ("post", f"/{SESSION}/abandon", "abandon", {}, 200),
]


def client_for(factory, role="student"):
    from backend.web.learning_dialog_providers import LearningDialogProviders

    app = create_app(
        learning_dialog_providers=LearningDialogProviders(usecases=factory),
        access_token_verifier=lambda token, cfg: {"sub": "learner", "realm_access": {"roles": [role]}},
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"Authorization": "Bearer test.jwt", "Origin": "http://test", "Idempotency-Key": "turn-1"})


@pytest.mark.parametrize("method,suffix,operation,payload,status", OPERATIONS)
async def test_all_dialog_operations_keep_their_explicit_service(method, suffix, operation, payload, status):
    calls = []

    def service(label):
        def call(**kwargs):
            calls.append((label, kwargs))
            return {"id": SESSION, "status": "active", "round_count": 0, "turns": []}
        return lambda: SimpleNamespace(**{operation: call})

    async with client_for(service("A")) as a, client_for(service("B")) as b:
        for client in (a, b, a):
            response = await client.request(method, BASE + suffix, **({"json": payload} if payload is not None else {}))
            assert response.status_code == status
            assert response.headers["cache-control"] == "private, no-store"
    assert [label for label, _ in calls] == ["A", "B", "A"]
    assert all(scope["student_sub"] == "learner" and scope["course_id"] == COURSE and scope["task_id"] == TASK for _, scope in calls)


@pytest.mark.parametrize("case,status", [("anonymous", 401), ("teacher", 403), ("csrf", 403), ("uuid", 400)])
async def test_rejection_precedes_service_construction(case, status):
    async with client_for(lambda: pytest.fail("unauthorized service construction"), "teacher" if case == "teacher" else "student") as client:
        if case == "anonymous":
            del client.headers["Authorization"]
        if case == "csrf":
            client.headers["Origin"] = "https://evil.example"
        response = await client.post(BASE.replace(COURSE, "invalid") if case == "uuid" else BASE)
        assert response.status_code == status


async def test_slow_dialog_does_not_block_unrelated_requests():
    entered, release = threading.Event(), threading.Event()

    def start(**kwargs):
        entered.set()
        assert release.wait(5)
        return {"id": SESSION, "status": "active", "turns": []}

    async with client_for(lambda: SimpleNamespace(start=start)) as client:
        pending = asyncio.create_task(client.post(BASE))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert (await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)).status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 201


def test_generator_and_usage_buffers_are_never_cached(monkeypatch):
    from backend.web import learning_dialog_providers as wiring

    repositories, generators = [], []

    def build_repo():
        repo = object()
        repositories.append(repo)
        return repo

    def build_generator():
        generator = object()
        generators.append(generator)
        return generator

    monkeypatch.setattr(wiring, "DBLearningRepo", build_repo)
    monkeypatch.setattr(wiring, "build_dialog_generator", build_generator)
    provider = wiring.create_learning_dialog_providers()
    assert not repositories and not generators
    first, second = provider.usecases(), provider.usecases()
    assert first is not second
    assert len(repositories) == 1 and len(generators) == 2
    assert first._repo is second._repo
    assert first._generator is not second._generator
