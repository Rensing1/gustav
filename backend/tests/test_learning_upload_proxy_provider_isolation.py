"""Upload forwarding must use explicit dependencies, never patched endpoint globals."""

import asyncio
import hashlib
import importlib
import inspect
import logging

import httpx
import pytest

from backend.web.learning_upload_proxy_providers import LearningUploadProxyProviders
from backend.web.main import create_app

pytestmark = pytest.mark.anyio("asyncio")
PATH = "/api/learning/internal/upload-proxy"
TARGET = "https://storage.example/storage/v1/object/upload/sign/submissions/file?token=secret"
upload_proxy = importlib.import_module("backend.web.routes.learning_upload_proxy")


@pytest.fixture(autouse=True)
def proxy_config(monkeypatch):
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://storage.example")
    monkeypatch.delenv("SUPABASE_PUBLIC_URL", raising=False)
    monkeypatch.setenv("LEARNING_UPLOAD_PROXY_TIMEOUT_SECONDS", "17")


def client_for(forward, emit, *, role="student"):
    app = create_app(
        learning_upload_proxy_providers=LearningUploadProxyProviders(forward=forward, emit=emit),
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


async def test_upload_uses_only_its_explicit_transport_and_telemetry():
    calls, events = [], []

    def dependencies(label):
        async def forward(**kwargs):
            calls.append((label, kwargs))
            return httpx.Response(200)

        def emit(**kwargs):
            events.append((label, kwargs))

        return forward, emit

    body = b"private upload bytes"
    async with client_for(*dependencies("A")) as a, client_for(*dependencies("B")) as b:
        for client in (a, b, a):
            response = await client.put(
                PATH,
                params={
                    "url": TARGET,
                    "headers": upload_proxy.encode_proxy_headers(
                        {
                            "x-upsert": "true",
                            "Content-Type": "image/png",
                            "Authorization": "secret",
                        }
                    ),
                },
                content=body,
                headers={"Content-Type": "image/png"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "sha256": hashlib.sha256(body).hexdigest(),
                "size_bytes": len(body),
            }
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["vary"] == "Origin"
    assert calls == [
        (
            label,
            {
                "url": TARGET,
                "payload": body,
                "content_type": "image/png",
                "timeout": 17.0,
                "headers": {"x-upsert": "true", "Content-Type": "image/png"},
            },
        )
        for label in ("A", "B", "A")
    ]
    assert events == [
        (
            label,
            {
                "outcome": "success",
                "status_code": 200,
                "reason": "ok",
                "target_host": "storage.example",
                "content_type": "image/png",
                "size_bytes": len(body),
            },
        )
        for label in ("A", "B", "A")
    ]


@pytest.mark.parametrize(
    "case,status",
    [
        ("anonymous", 401),
        ("teacher", 403),
        ("csrf", 403),
        ("disabled", 404),
        ("host", 400),
    ],
)
async def test_rejected_upload_never_reaches_transport(monkeypatch, case, status):
    calls, events = [], []

    async def forward(**kwargs):
        calls.append(kwargs)
        return httpx.Response(200)

    async with client_for(
        forward,
        lambda **kwargs: events.append(kwargs),
        role="teacher" if case == "teacher" else "student",
    ) as client:
        if case == "anonymous":
            del client.headers["Authorization"]
        if case == "csrf":
            client.headers["Origin"] = "https://evil.example"
        if case == "disabled":
            monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
        target = TARGET.replace("storage.example", "evil.example") if case == "host" else TARGET
        response = await client.put(PATH, params={"url": target}, content=b"abc")
    assert response.status_code == status
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Origin"
    assert not calls
    # Anonymous requests are rejected by middleware before the route is entered.
    if case == "anonymous":
        assert not events
        return
    assert len(events) == 1
    assert events[0]["status_code"] == status
    assert events[0]["outcome"] == "error"


@pytest.mark.parametrize(
    "failure,detail", [("exception", "proxy_failed"), ("status", "upstream_error")]
)
async def test_upstream_failure_uses_same_private_contract(failure, detail):
    events = []

    async def forward(**kwargs):
        if failure == "exception":
            raise RuntimeError("secret upstream diagnostics")
        return httpx.Response(500)

    async with client_for(forward, lambda **kwargs: events.append(kwargs)) as client:
        response = await client.put(PATH, params={"url": TARGET}, content=b"abc")
    assert response.status_code == 502
    assert response.json() == {"error": "bad_gateway", "detail": detail}
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Origin"
    assert events[0]["reason"] == detail
    assert "secret" not in repr(events)


async def test_waiting_transport_keeps_shell_responsive():
    started, release = asyncio.Event(), asyncio.Event()

    async def forward(**kwargs):
        started.set()
        await release.wait()
        return httpx.Response(200)

    async with client_for(forward, lambda **kwargs: None) as client:
        pending = asyncio.create_task(client.put(PATH, params={"url": TARGET}, content=b"abc"))
        try:
            await asyncio.wait_for(started.wait(), 2)
            response = await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            assert response.status_code == 200
        finally:
            release.set()
            result = await pending
        assert result.status_code == 200


def test_standard_provider_uses_canonical_transport_and_logger(caplog, monkeypatch):
    wiring = importlib.import_module("backend.web.learning_upload_proxy_providers")
    helpers = importlib.import_module("backend.web.routes.learning_upload_proxy")
    provider = wiring.create_learning_upload_proxy_providers()
    assert provider.forward is helpers.async_forward_upload
    assert provider.emit is helpers.emit_upload_proxy_telemetry
    event = dict(
        outcome="error",
        status_code=502,
        reason="proxy_failed",
        target_host="storage.example",
        content_type="image/png",
        size_bytes=None,
    )
    with caplog.at_level(logging.INFO, logger="gustav.web.learning"):
        provider.emit(**event)
    assert (
        caplog.records[-1].getMessage()
        == "learning.upload_proxy outcome=error status=502 reason=proxy_failed host=storage.example mime=image/png size_bytes=-1"
    )

    def broken_logger(*args, **kwargs):
        raise RuntimeError("logging unavailable")

    monkeypatch.setattr(logging.getLogger("gustav.web.learning"), "info", broken_logger)
    provider.emit(**event)


def test_transport_and_telemetry_need_no_legacy_resolution():
    learning = importlib.import_module("backend.web.routes.learning")
    routes = importlib.import_module("backend.web.routes.learning_internal_upload_routes")
    for name in (
        "_current_async_forward_upload",
        "_current_emit_upload_proxy_telemetry",
        "_async_forward_upload",
        "_emit_upload_proxy_telemetry",
    ):
        assert not hasattr(learning, name)
        assert not hasattr(routes, name)
    assert "globals()" not in inspect.getsource(routes)
    assert "learning_upload_proxy_providers(request)" in inspect.getsource(
        routes.internal_upload_proxy
    )
