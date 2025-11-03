"""
Health probe utilities for the learning worker.

Intent:
    Provide a lightweight service that verifies the worker's prerequisites
    (database role, queue visibility) without leaking implementation details
    into the FastAPI layer. The service is async-friendly so the web adapter
    can await it without blocking the event loop.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from typing import Callable, List, Optional

try:  # pragma: no cover - optional dependency
    import psycopg
    from psycopg.rows import dict_row
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False


def _default_dsn() -> str:
    env = os.getenv("LEARNING_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env:
        return env
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


@dataclass(frozen=True)
class HealthCheckResult:
    check: str
    status: str
    detail: Optional[str] = None


@dataclass(frozen=True)
class HealthProbeResult:
    status: str
    current_role: Optional[str]
    checks: List[HealthCheckResult]


class LearningWorkerHealthService:
    """Evaluate the readiness of the learning worker pipeline."""

    def __init__(self, dsn_resolver: Callable[[], str] | None = None):
        self._dsn_resolver = dsn_resolver or _default_dsn

    async def probe(self) -> HealthProbeResult:
        """Run the health probe in a thread to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._probe_sync)

    def _probe_sync(self) -> HealthProbeResult:
        """Perform the blocking probe against Postgres and return aggregated results.

        Why:
            The web adapter runs inside FastAPI (async). To keep the code simple we use
            psycopg's blocking client but execute it in a thread via `probe()`.
        """
        if not HAVE_PSYCOPG:
            return HealthProbeResult(
                status="degraded",
                current_role=None,
                checks=[
                    HealthCheckResult(
                        check="db_role",
                        status="failed",
                        detail="psycopg3 not installed on web worker",
                    )
                ],
            )

        dsn = self._dsn_resolver()
        checks: List[HealthCheckResult] = []
        current_role: Optional[str] = None

        rows: list[dict] = []
        try:
            with psycopg.connect(dsn, row_factory=dict_row) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute("select current_user")
                    row = cur.fetchone()
                    if row:
                        current_role = row.get("current_user")

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select check_name, status, detail
                          from public.learning_worker_health_probe()
                        """
                    )
                    rows = cur.fetchall()
        except Exception as exc:  # pragma: no cover - defensive
            checks.append(
                HealthCheckResult(
                    check="db_role",
                    status="failed",
                    detail=f"probe_error: {exc}",
                )
            )
            return HealthProbeResult(status="degraded", current_role=current_role, checks=checks)

        for row in rows:
            checks.append(
                HealthCheckResult(
                    check=str(row.get("check_name")),
                    status=str(row.get("status")),
                    detail=row.get("detail"),
                )
            )

        overall = "healthy" if all(check.status == "ok" for check in checks) else "degraded"
        return HealthProbeResult(status=overall, current_role=current_role, checks=checks)


LEARNING_WORKER_HEALTH_SERVICE = LearningWorkerHealthService()

__all__ = [
    "HealthCheckResult",
    "HealthProbeResult",
    "LearningWorkerHealthService",
    "LEARNING_WORKER_HEALTH_SERVICE",
]
