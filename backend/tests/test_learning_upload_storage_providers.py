"""Upload signing uses explicit storage, retries failures and never rewires routes."""

import importlib
from types import SimpleNamespace

import httpx
import pytest

from backend.web.learning_upload_intent_providers import LearningUploadIntentProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
PATH = "/api/learning/courses/00000000-0000-0000-0000-000000000001/tasks/00000000-0000-0000-0000-000000000002/upload-intents"
PAYLOAD = {"kind": "image", "filename": "a.png", "mime_type": "image/png", "size_bytes": 10}


def client_for(storage):
    providers = LearningUploadIntentProviders(
        repository=lambda: SimpleNamespace(list_submissions=lambda **kwargs: []),
        storage=storage,
    )
    app = create_app(
        learning_upload_intent_providers=providers,
        access_token_verifier=lambda token, cfg: {"sub": "learner", "realm_access": {"roles": ["student"]}},
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": "Bearer test.jwt", "Origin": "http://test"},
    )


async def test_alternating_signers_ignore_legacy_storage(monkeypatch):
    learning = importlib.import_module("backend.web.routes.learning")

    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    calls = []

    def storage(label):
        def sign(**kwargs):
            calls.append((label, kwargs["bucket"]))
            return {"url": f"https://storage.example/{label}", "headers": kwargs["headers"]}
        return lambda: SimpleNamespace(presign_upload=sign)

    async with client_for(storage("A")) as a, client_for(storage("B")) as b:
        monkeypatch.setattr(learning, "_current_storage_adapter", lambda: pytest.fail("global storage read"))
        monkeypatch.setattr(learning, "_wire_storage", lambda: pytest.fail("global storage write"))
        for client, label in ((a, "A"), (b, "B"), (a, "A")):
            response = await client.post(PATH, json=PAYLOAD)
            assert response.status_code == 200
            assert response.json()["url"] == f"https://storage.example/{label}"
    assert calls == [("A", "submissions"), ("B", "submissions"), ("A", "submissions")]


async def test_storage_failure_is_private_and_retryable(monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    attempts = []

    def storage():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("sensitive configuration")
        return SimpleNamespace(presign_upload=lambda **kwargs: {"url": "https://storage.example/upload"})

    async with client_for(storage) as client:
        failed = await client.post(PATH, json=PAYLOAD)
        assert failed.status_code == 503
        assert failed.json() == {"error": "service_unavailable", "detail": "storage_adapter_not_configured"}
        assert failed.headers["cache-control"] == "private, no-store"
        assert (await client.post(PATH, json=PAYLOAD)).status_code == 200
    assert len(attempts) == 2


async def test_invalid_mime_never_initializes_storage():
    async with client_for(lambda: pytest.fail("invalid MIME reached storage")) as client:
        response = await client.post(PATH, json={**PAYLOAD, "mime_type": "image/gif"})
    assert response.status_code == 400


def test_default_storage_is_lazy_and_only_caches_success(monkeypatch):
    import backend.web.learning_upload_intent_providers as wiring

    calls = []
    adapter = object()

    def build():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return adapter

    monkeypatch.setattr(wiring, "build_storage_adapter", build)
    providers = wiring.create_learning_upload_intent_providers()
    assert calls == []
    with pytest.raises(RuntimeError):
        providers.storage()
    assert providers.storage() is providers.storage() is adapter
    assert len(calls) == 2
