"""
Learning worker health endpoint — contract tests.

Why:
    Ensure the internal health probe exposes the OpenAPI contract. Guards:
    - authenticated teacher/operator only
    - proper status/body mapping for healthy vs degraded worker states.
"""
from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store

from backend.learning.workers import health as worker_health

main = importlib.import_module("backend.web.main")

pytestmark = pytest.mark.anyio("asyncio")


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
    store = install_session_store(monkeypatch, main)
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
    store = install_session_store(monkeypatch, main)
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
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="teacher-health-db-fail", roles=["teacher"], name="Lehrkraft")

    # Force the service into the DB path and make connect() raise
    class _BadPsy:
        def connect(*args, **kwargs):  # noqa: ANN001 - test stub
            raise RuntimeError("boom")

    monkeypatch.setattr(worker_health, "HAVE_PSYCOPG", True, raising=False)
    monkeypatch.setattr(worker_health, "psycopg", _BadPsy, raising=False)
    monkeypatch.setattr(worker_health, "dict_row", object(), raising=False)

    # Keep the endpoint contract test deterministic by avoiding threadpool shutdown
    # edge-cases in the AnyIO test runner. We still exercise the same sync probe
    # branch (`db_connect_failed`) but call it directly in-process.
    class _SyncProbeHealthService(worker_health.LearningWorkerHealthService):
        async def probe(self) -> worker_health.HealthProbeResult:  # type: ignore[override]
            return self._probe_sync()

    monkeypatch.setattr(
        worker_health,
        "LEARNING_WORKER_HEALTH_SERVICE",
        _SyncProbeHealthService(),
        raising=False,
    )

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
    install_session_store(monkeypatch, main)
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


@pytest.mark.anyio
async def test_learning_worker_health_service_probe_uses_run_in_executor(monkeypatch: pytest.MonkeyPatch):
    """Service probe should delegate blocking work via run_in_executor."""
    expected = _probe_result(
        status="healthy",
        current_role="gustav_worker",
        checks=[("db_role", "ok", None)],
    )
    calls: dict[str, object] = {}

    class _FakeLoop:
        async def run_in_executor(self, executor, fn):  # noqa: ANN001 - test double mirrors asyncio API
            calls["executor"] = executor
            calls["fn"] = fn
            return expected

    monkeypatch.setattr(worker_health.asyncio, "get_running_loop", lambda: _FakeLoop(), raising=True)
    service = worker_health.LearningWorkerHealthService()

    result = await service.probe()

    assert result == expected
    assert calls.get("executor") is None
    fn = calls.get("fn")
    assert callable(fn)
    assert getattr(fn, "__name__", "") == "_probe_sync"
    assert getattr(fn, "__self__", None) is service


def test_learning_worker_health_service_marks_app_role_as_degraded(monkeypatch: pytest.MonkeyPatch):
    """The health service must reject app-role drift even when queue visibility is fine."""

    class _Cursor:
        def __init__(self, rows):
            self._rows = list(rows)

        def execute(self, _sql):  # noqa: ANN001 - test double mirrors psycopg cursor
            return None

        def fetchone(self):
            if not self._rows:
                return None
            return self._rows.pop(0)

        def fetchall(self):
            if not self._rows:
                return []
            return self._rows.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Connection:
        def __init__(self):
            self._cursor_index = 0

        def cursor(self):
            self._cursor_index += 1
            if self._cursor_index == 1:
                return _Cursor([{"current_user": "gustav_app"}])
            return _Cursor([[{"check_name": "queue_visibility", "status": "ok", "detail": "visible_jobs=0"}]])

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakePsy:
        @staticmethod
        def connect(*args, **kwargs):  # noqa: ANN001 - test stub mirrors psycopg API
            return _Connection()

    monkeypatch.setattr(worker_health, "HAVE_PSYCOPG", True, raising=False)
    monkeypatch.setattr(worker_health, "psycopg", _FakePsy, raising=False)
    monkeypatch.setattr(worker_health, "dict_row", object(), raising=False)

    service = worker_health.LearningWorkerHealthService(dsn_resolver=lambda: "postgresql://gustav_worker:pw@db:5432/postgres")

    result = service._probe_sync()

    assert result.status == "degraded"
    assert result.current_role == "gustav_app"
    assert result.checks == [
        worker_health.HealthCheckResult(
            check="db_role",
            status="failed",
            detail="expected gustav_worker, got gustav_app",
        ),
        worker_health.HealthCheckResult(
            check="queue_visibility",
            status="ok",
            detail="visible_jobs=0",
        ),
    ]
