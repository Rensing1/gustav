"""Helpers for keeping DB-backed tests scoped to their own rows.

Why:
    Several tests run against the same real Postgres/Supabase database as the
    application. These helpers make the test ownership explicit so cleanup can
    target only rows created by the current test run.
"""

from __future__ import annotations

import os
import re
from uuid import uuid4


def current_test_run_id() -> str:
    """Return a stable identifier for rows created by the current pytest case."""

    explicit = (os.getenv("GUSTAV_TEST_RUN_ID") or "").strip()
    if explicit:
        return explicit
    current = (os.getenv("PYTEST_CURRENT_TEST") or "").strip()
    if current:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "-", current)[:180]
    generated = f"pytest-{uuid4()}"
    os.environ["GUSTAV_TEST_RUN_ID"] = generated
    return generated


def cleanup_learning_jobs_for_run(conn, test_run_id: str | None = None) -> int:  # noqa: ANN001
    """Delete only queue jobs tagged with the current test-run id."""

    run_id = test_run_id or current_test_run_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from public.learning_submission_jobs
             where payload->>'_gustav_test_run_id' = %s
            """,
            (run_id,),
        )
        return int(cur.rowcount or 0)
