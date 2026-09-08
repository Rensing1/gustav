"""Upload authorization uses one explicit repository without blocking the event loop."""

import asyncio
import importlib
import inspect
import threading
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from backend.tests.learning_route_helpers import VisibleLearningRepo
from backend.web.learning_upload_intent_providers import LearningUploadIntentProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
COURSE, TASK = str(uuid4()), str(uuid4())
PATH = f"/api/learning/courses/{COURSE}/tasks/{TASK}/upload-intents"
PAYLOAD = {"kind": "image", "filename": "bild.png", "mime_type": "image/png", "size_bytes": 10}


@pytest.fixture
def storage(monkeypatch):
    """Replace only signing; shared storage initialization is a later migration."""
    routes = importlib.import_module("backend.web.routes.learning_upload_intents")
    calls = []

    def presign(**kwargs):
        calls.append(kwargs)
        return {"url": "https://storage.example/upload", "headers": kwargs["headers"]}

    adapter = SimpleNamespace(presign_upload=presign, calls=calls)
    monkeypatch.setattr(routes, "_current_storage_adapter", lambda: adapter)
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("LEARNING_MAX_UPLOAD_BYTES", "100")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    return adapter


def client_for(factory, *, role="student"):
    app = create_app(
        learning_upload_intent_providers=LearningUploadIntentProviders(repository=factory),
        access_token_verifier=lambda token, cfg: {
            "sub": "learner",
            "realm_access": {"roles": [role]},
        },
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt", "Origin": "http://test"},
    )


async def test_each_request_resolves_one_repository_for_both_reads(monkeypatch, storage):
    calls = []

    def factory(label):
        def build():
            calls.append((label, "build", {}))

            def read(phase, **kwargs):
                calls.append((label, phase, kwargs))
                return [] if phase == "list" else "native"

            return SimpleNamespace(
                list_submissions=lambda **kwargs: read("list", **kwargs),
                get_task_kind_for_student=lambda **kwargs: read("kind", **kwargs),
            )

        return build

    async with client_for(factory("A")) as a, client_for(factory("B")) as b:
        learning = importlib.import_module("backend.web.routes.learning")
        monkeypatch.setattr(
            learning, "_get_repo", lambda: pytest.fail("legacy repository accessed")
        )
        for client in (a, b, a):
            response = await client.post(PATH, json=PAYLOAD)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["vary"] == "Origin"
    scope = {"student_sub": "learner", "course_id": COURSE, "task_id": TASK}
    assert calls == [
        item
        for label in ("A", "B", "A")
        for item in (
            (label, "build", {}),
            (label, "list", {**scope, "limit": 1, "offset": 0}),
            (label, "kind", scope),
        )
    ]
    assert len(storage.calls) == 3


@pytest.mark.parametrize(
    "case,status",
    [
        ("anonymous", 401),
        ("teacher", 404),
        ("csrf", 403),
        ("uuid", 400),
        ("filename", 400),
        ("size", 400),
        ("zero", 400),
        ("kind", 400),
    ],
)
async def test_rejection_precedes_repository_and_signing(case, status, storage):
    async with client_for(
        lambda: pytest.fail("invalid request reached DB"),
        role="teacher" if case == "teacher" else "student",
    ) as client:
        payload = dict(PAYLOAD)
        path = PATH
        if case == "anonymous":
            del client.headers["Authorization"]
        elif case == "csrf":
            client.headers["Origin"] = "https://evil.example"
        elif case == "uuid":
            path = PATH.replace(COURSE, "bad")
        elif case == "filename":
            payload["filename"] = ""
        elif case in ("size", "zero"):
            payload["size_bytes"] = 101 if case == "size" else 0
        elif case == "kind":
            payload["kind"] = "text"
        response = await client.post(path, json=payload)
    assert response.status_code == status
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Origin"
    assert not storage.calls


@pytest.mark.parametrize("phase", ["build", "list", "kind"])
@pytest.mark.parametrize(
    "error,status", [(PermissionError, 404), (LookupError, 404), (RuntimeError, 503)]
)
async def test_repository_failures_never_sign(phase, error, status, storage):
    def fail():
        raise error("private diagnostics")

    def factory():
        if phase == "build":
            fail()
        return SimpleNamespace(
            list_submissions=lambda **kwargs: fail() if phase == "list" else [],
            get_task_kind_for_student=lambda **kwargs: fail() if phase == "kind" else "native",
        )

    async with client_for(factory) as client:
        response = await client.post(PATH, json=PAYLOAD)
    assert response.status_code == status
    assert response.json() == (
        {"error": "not_found"}
        if status == 404
        else {"error": "service_unavailable", "detail": "authorization_unavailable"}
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Origin"
    assert not storage.calls


@pytest.mark.parametrize(
    "task_kind,kind,mime,ext",
    [
        ("native", "image", "image/png", ".png"),
        ("native", "image", "image/jpeg", ".jpg"),
        ("native", "file", "application/pdf", ".pdf"),
        ("scratch", "file", "application/x.scratch.sb3", ".sb3"),
        ("calliope", "file", "application/x.makecode.hex", ".hex"),
        ("filius", "file", "application/x.filius.fls", ".fls"),
    ],
)
async def test_task_kind_policy_and_size_boundary_are_preserved(
    task_kind, kind, mime, ext, storage
):
    repo = SimpleNamespace(
        list_submissions=lambda **kwargs: [], get_task_kind_for_student=lambda **kwargs: task_kind
    )
    async with client_for(lambda: repo) as client:
        response = await client.post(
            PATH, json={**PAYLOAD, "kind": kind, "mime_type": mime, "size_bytes": 100}
        )
        assert response.status_code == 200
        assert response.json()["storage_key"].endswith(ext)
        assert mime in response.json()["accepted_mime_types"]
        rejected = await client.post(PATH, json={**PAYLOAD, "mime_type": "image/gif"})
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "mime_not_allowed"
    assert len(storage.calls) == 1


@pytest.mark.parametrize("phase", ["build", "list", "kind", "sign"])
async def test_synchronous_work_keeps_shell_responsive(phase, storage):
    started, release = threading.Event(), threading.Event()

    def wait():
        started.set()
        assert release.wait(5)

    def factory():
        if phase == "build":
            wait()

        def read(**kwargs):
            if phase == "list":
                wait()
            return []

        def kind(**kwargs):
            if phase == "kind":
                wait()
            return "native"

        return SimpleNamespace(list_submissions=read, get_task_kind_for_student=kind)

    sign = storage.presign_upload
    if phase == "sign":

        def delayed_sign(**kwargs):
            wait()
            return sign(**kwargs)

        storage.presign_upload = delayed_sign
    async with client_for(factory) as client:
        pending = asyncio.create_task(client.post(PATH, json=PAYLOAD))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            response = await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            assert response.status_code == 200
        finally:
            release.set()
            result = await pending
        assert result.status_code == 200


def test_default_repository_is_lazy_and_failed_construction_remains_retryable(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_upload_intent_providers")
    calls, repo = [], VisibleLearningRepo()

    def build():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("DB unavailable")
        return repo

    monkeypatch.setattr(wiring, "DBLearningRepo", build)
    provider = wiring.create_learning_upload_intent_providers()
    assert not calls
    with pytest.raises(RuntimeError):
        provider.repository()
    assert provider.repository() is provider.repository() is repo
    assert len(calls) == 2


def test_upload_handler_needs_no_legacy_repository_or_use_case_lookup():
    routes = importlib.import_module("backend.web.routes.learning_upload_intents")
    assert not inspect.iscoroutinefunction(routes.create_upload_intent)
    for name in ("_get_repo", "_list_submissions_use_case", "_list_submissions_input"):
        assert not hasattr(routes, name)
