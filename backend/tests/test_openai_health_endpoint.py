"""
OpenAI health endpoint — contract tests (SSR/internal).

Why:
    Lehrkräfte sollen im UI (Fußleiste) schnell sehen können, ob die
    konfigurierte KI-URL erreichbar ist und ob dort Modelle verfügbar sind.

Security:
    - teacher/operator only
    - private/no-store caching
"""

from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


def _install_session_store() -> SessionStore:
    store = SessionStore()
    main.SESSION_STORE = store
    return store


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


class _FakeProbe:
    def __init__(self, body: dict, status_code: int):
        self.body = body
        self.status_code = status_code
        self.calls = 0

    async def __call__(self) -> tuple[dict, int]:
        self.calls += 1
        return self.body, self.status_code


@pytest.mark.anyio
async def test_openai_health_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unauthenticated callers must receive 401 and the probe must not run."""
    _install_session_store()
    import routes.operations as operations  # type: ignore  # noqa: E402

    fake = _FakeProbe({"status": "healthy"}, 200)
    monkeypatch.setattr(operations, "_probe_openai_health", fake, raising=False)

    async with await _client() as client:
        resp = await client.get("/internal/health/openai")

    assert resp.status_code == 401
    assert fake.calls == 0
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_openai_health_requires_teacher_or_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Students must not see internal diagnostics."""
    store = _install_session_store()
    student = store.create(sub="s-openai", roles=["student"], name="S")
    import routes.operations as operations  # type: ignore  # noqa: E402

    fake = _FakeProbe({"status": "healthy"}, 200)
    monkeypatch.setattr(operations, "_probe_openai_health", fake, raising=False)

    async with await _client() as client:
        client.cookies.set("gustav_session", student.session_id)
        resp = await client.get("/internal/health/openai")

    assert resp.status_code == 403
    assert fake.calls == 0
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_openai_health_returns_healthy_payload_for_teachers(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _install_session_store()
    teacher = store.create(sub="t-openai", roles=["teacher"], name="T")
    import routes.operations as operations  # type: ignore  # noqa: E402

    body = {
        "status": "healthy",
        "configured": True,
        "reachable": True,
        "modelsLoaded": True,
        "modelsCount": 3,
        "detail": None,
    }
    fake = _FakeProbe(body, 200)
    monkeypatch.setattr(operations, "_probe_openai_health", fake, raising=False)

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.get("/internal/health/openai")

    assert resp.status_code == 200
    assert fake.calls == 1
    assert resp.json() == body
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_openai_health_returns_503_for_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _install_session_store()
    teacher = store.create(sub="t-openai-degraded", roles=["teacher"], name="T")
    import routes.operations as operations  # type: ignore  # noqa: E402

    body = {
        "status": "degraded",
        "configured": True,
        "reachable": False,
        "modelsLoaded": False,
        "modelsCount": 0,
        "detail": "connect_failed",
    }
    fake = _FakeProbe(body, 503)
    monkeypatch.setattr(operations, "_probe_openai_health", fake, raising=False)

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.get("/internal/health/openai")

    assert resp.status_code == 503
    assert fake.calls == 1
    assert resp.json() == body
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_openai_health_caches_probe_result_for_short_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The footer indicator polls periodically; the endpoint should avoid hammering
    the OpenAI-compatible endpoint when multiple requests happen close together.
    """
    store = _install_session_store()
    teacher = store.create(sub="t-openai-cache", roles=["teacher"], name="T")
    import routes.operations as operations  # type: ignore  # noqa: E402

    fake = _FakeProbe({"status": "healthy", "configured": True, "reachable": True, "modelsLoaded": True, "modelsCount": 1, "detail": None}, 200)
    monkeypatch.setattr(operations, "_probe_openai_health", fake, raising=False)

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        r1 = await client.get("/internal/health/openai")
        r2 = await client.get("/internal/health/openai")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert fake.calls == 1, "expected probe to be cached between close calls"


@pytest.mark.anyio
async def test_openai_health_ignores_stale_cache_from_previous_probe_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cache row from another probe callable must never bleed into this request."""
    store = _install_session_store()
    teacher = store.create(sub="t-openai-cache-isolation", roles=["teacher"], name="T")
    import routes.operations as operations  # type: ignore  # noqa: E402

    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
    stale_body = {
        "status": "degraded",
        "configured": True,
        "reachable": False,
        "modelsLoaded": False,
        "modelsCount": 0,
        "detail": "stale",
    }
    stale_probe = _FakeProbe(stale_body, 503)
    now = time.monotonic()
    monkeypatch.setitem(operations._OPENAI_HEALTH_CACHE, "key", (base_url, stale_probe))
    monkeypatch.setitem(operations._OPENAI_HEALTH_CACHE, "at", now)
    monkeypatch.setitem(operations._OPENAI_HEALTH_CACHE, "body", dict(stale_body))
    monkeypatch.setitem(operations._OPENAI_HEALTH_CACHE, "status_code", 503)

    fresh_body = {
        "status": "healthy",
        "configured": True,
        "reachable": True,
        "modelsLoaded": True,
        "modelsCount": 1,
        "detail": None,
    }
    fresh_probe = _FakeProbe(fresh_body, 200)
    monkeypatch.setattr(operations, "_probe_openai_health", fresh_probe, raising=False)

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.get("/internal/health/openai")

    assert resp.status_code == 200
    assert resp.json() == fresh_body
    assert fresh_probe.calls == 1


@pytest.mark.anyio
async def test_probe_openai_health_disables_trust_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Probe should not inherit proxy settings from the environment."""
    _install_session_store()
    import routes.operations as operations  # type: ignore  # noqa: E402

    observed: dict = {}

    class _FakeHTTPXResponse:
        def __init__(self, status_code: int, payload: object):
            self.status_code = status_code
            self._payload = payload

        def json(self):  # type: ignore[no-untyped-def]
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, **kwargs):
            observed["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, headers: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
            observed["url"] = url
            observed["headers"] = headers or {}
            return _FakeHTTPXResponse(200, {"data": [{"id": "m1"}]})

    fake_httpx = types.SimpleNamespace(AsyncClient=lambda **kwargs: _FakeAsyncClient(**kwargs))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.com/api/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    body, status_code = await operations._probe_openai_health()
    assert status_code == 200
    assert body.get("modelsCount") == 1

    client_kwargs = observed.get("client_kwargs") or {}
    assert client_kwargs.get("trust_env") is False
