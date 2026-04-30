"""DB contract for AI token usage accounting.

Why:
    Token usage is sensitive learner telemetry. The database must store only
    technical counters, derive course context from the submission, and expose
    teacher reads through RLS instead of a broad SECURITY DEFINER aggregate.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_ai_usage_events_table_constraints_and_worker_helper_exist() -> None:
    _require_db_or_skip()

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.ai_usage_events')::text")
            assert (cur.fetchone() or [None])[0] == "ai_usage_events"

            cur.execute(
                """
                select column_name
                  from information_schema.columns
                 where table_schema = 'public'
                   and table_name = 'ai_usage_events'
                 order by ordinal_position
                """
            )
            columns = {row[0] for row in cur.fetchall()}
            assert {
                "id",
                "event_key",
                "occurred_at",
                "submission_id",
                "course_id",
                "unit_id",
                "task_id",
                "student_sub",
                "model",
                "stage",
                "modality",
                "call_kind",
                "usage_known",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "unknown_reason",
            } <= columns

            cur.execute(
                """
                select conname, pg_get_constraintdef(oid)
                  from pg_constraint
                 where conrelid = 'public.ai_usage_events'::regclass
                """
            )
            constraint_defs = " ".join(f"{name} {definition}" for name, definition in cur.fetchall())
            assert "ai_usage_events_usage_known_shape" in constraint_defs
            assert "ai_usage_events_stage_check" in constraint_defs
            assert "ai_usage_events_modality_check" in constraint_defs
            assert "ai_usage_events_call_kind_check" in constraint_defs

            cur.execute(
                """
                select relrowsecurity
                  from pg_class
                 where oid = 'public.ai_usage_events'::regclass
                """
            )
            assert bool((cur.fetchone() or [False])[0]) is True

            cur.execute(
                """
                select has_function_privilege(
                    'gustav_worker',
                    'public.learning_worker_record_ai_usage(uuid, uuid, text, text, text, text, boolean, integer, integer, integer, text)',
                    'execute'
                )
                """
            )
            assert bool((cur.fetchone() or [False])[0]) is True


@pytest.mark.anyio
async def test_no_teacher_facing_security_definer_ai_usage_aggregate() -> None:
    _require_db_or_skip()

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select proname
                  from pg_proc p
                  join pg_namespace n on n.oid = p.pronamespace
                 where n.nspname = 'public'
                   and p.proname like '%ai_usage%'
                   and p.prosecdef
                   and p.proname <> 'learning_worker_record_ai_usage'
                """
            )
            assert cur.fetchall() == []
