"""
Learning worker health endpoint — contract tests.

Why:
    Ensure the internal health probe exposes the OpenAPI contract. Guards:
    - authenticated teacher/operator only
    - proper status/body mapping for healthy vs degraded worker states.
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

from backend.learning.workers import health as worker_health  # noqa: E402  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _install_session_store() -> SessionStore:
    store = SessionStore()
    main.SESSION_STORE = store
    return store


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


def _probe_result(
    *,
    status: str,
    current_role: str | None,
    checks: list[tuple[str, str, str | None]],
) -> worker_health.HealthProbeResult:
    """Helper to produce a structured probe result for tests."""
    return worker_health.HealthProbeResult(
        status=status,
        current_role=current_role,
        checks=[
            worker_health.HealthCheckResult(check=name, status=chk_status, detail=detail)
            for name, chk_status, detail in checks
        ],
    )


class _FakeHealthService:
    def __init__(self, result: worker_health.HealthProbeResult):
        self._result = result
        self.probe_calls = 0

    async def probe(self) -> worker_health.HealthProbeResult:
        self.probe_calls += 1
        return self._result


@pytest.mark.anyio
async def test_learning_worker_health_returns_healthy(monkeypatch: pytest.MonkeyPatch):
    """Authorized teachers should receive the healthy payload when probe passes."""
    store = _install_session_store()
    teacher = store.create(sub="teacher-health", roles=["teacher"], name="Lehrkraft")

    fake_result = _probe_result(
        status="healthy",
        current_role="gustav_worker",
        checks=[
            ("db_role", "ok", None),
            ("queue_visibility", "ok", None),
        ],
    )
    fake_service = _FakeHealthService(fake_result)
    monkeypatch.setattr(worker_health, "LEARNING_WORKER_HEALTH_SERVICE", fake_service)

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.get("/internal/health/learning-worker")

    assert resp.status_code == 200
    assert fake_service.probe_calls == 1
    assert resp.json() == {
        "status": "healthy",
        "currentRole": "gustav_worker",
        "checks": [
            {"check": "db_role", "status": "ok", "detail": None},
            {"check": "queue_visibility", "status": "ok", "detail": None},
        ],
    }
    # Security headers
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_learning_worker_health_returns_503_when_role_missing(monkeypatch: pytest.MonkeyPatch):
    """If the worker role is missing, the probe must surface degraded status."""
    store = _install_session_store()
    teacher = store.create(sub="teacher-health-missing", roles=["teacher"], name="Lehrkraft")

    fake_result = _probe_result(
        status="degraded",
        current_role=None,
        checks=[
            ("db_role", "failed", "gustav_worker role not available"),
        ],
    )
    monkeypatch.setattr(
        worker_health,
        "LEARNING_WORKER_HEALTH_SERVICE",
        _FakeHealthService(fake_result),
    )

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.get("/internal/health/learning-worker")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "degraded",
        "currentRole": None,
        "checks": [
            {
                "check": "db_role",
                "status": "failed",
                "detail": "gustav_worker role not available",
            }
        ],
    }
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_learning_worker_health_returns_503_on_db_failure(monkeypatch: pytest.MonkeyPatch):
    """DB connection failures degrade the probe and return 503 with private headers.

    We simulate psycopg being available but raising on connect, to exercise the
    `db_connect_failed` branch in the health service.
    """
    store = _install_session_store()
    teacher = store.create(sub="teacher-health-db-fail", roles=["teacher"], name="Lehrkraft")

    # Force the service into the DB path and make connect() raise
    class _BadPsy:
        def connect(*args, **kwargs):  # noqa: ANN001 - test stub
            raise RuntimeError("boom")

    monkeypatch.setattr(worker_health, "HAVE_PSYCOPG", True, raising=False)
    monkeypatch.setattr(worker_health, "psycopg", _BadPsy, raising=False)
    monkeypatch.setattr(worker_health, "dict_row", object(), raising=False)

    async with await _client() as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.get("/internal/health/learning-worker")

    assert resp.status_code == 503
    body = resp.json()
    assert body.get("status") == "degraded"
    # db_connect_failed detail is acceptable to expose and non-sensitive
    assert body.get("checks") == [
        {"check": "db_role", "status": "failed", "detail": "db_connect_failed"}
    ]
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"


@pytest.mark.anyio
async def test_learning_worker_health_requires_authentication(monkeypatch: pytest.MonkeyPatch):
    """Unauthenticated callers must receive 401 without hitting the probe."""
    _install_session_store()
    fake_service = _FakeHealthService(
        _probe_result(
            status="healthy",
            current_role="gustav_worker",
            checks=[("db_role", "ok", None)],
        )
    )
    monkeypatch.setattr(worker_health, "LEARNING_WORKER_HEALTH_SERVICE", fake_service)

    async with await _client() as client:
        resp = await client.get("/internal/health/learning-worker")

    assert resp.status_code == 401
    assert fake_service.probe_calls == 0
    assert resp.headers.get("Cache-Control") == "private, no-store"
    assert resp.headers.get("Vary") == "Origin"
