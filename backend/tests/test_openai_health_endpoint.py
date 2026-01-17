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

import sys
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

