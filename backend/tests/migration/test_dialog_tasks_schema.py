"""Database contract for dialog-task configuration and learner sessions.

Why:
    Dialogs persist mutable work before an immutable submission. The schema
    must keep author-only prompts separate from learner-visible transcripts and
    enforce course-scoped ownership and concurrency invariants in PostgreSQL.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402


pytestmark = pytest.mark.db_read


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_dialog_tables_columns_constraints_and_rls_exist() -> None:
    _require_db_or_skip()

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            for table in (
                "unit_task_dialog_configs",
                "learning_dialog_sessions",
                "learning_dialog_session_contexts",
                "learning_dialog_turns",
                "dialog_ai_usage_events",
            ):
                cur.execute("select to_regclass(%s)::text", (f"public.{table}",))
                assert (cur.fetchone() or [None])[0] == table
                cur.execute("select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{table}",))
                assert bool((cur.fetchone() or [False])[0]) is True

            cur.execute(
                """
                select column_name
                  from information_schema.columns
                 where table_schema = 'public'
                   and table_name = 'learning_dialog_sessions'
                """
            )
            session_columns = {row[0] for row in cur.fetchall()}
            assert {"course_id", "task_id", "student_sub", "status", "round_count"} <= session_columns
            assert "config_snapshot" not in session_columns

            cur.execute(
                """
                select a.attname
                  from pg_catalog.pg_attribute a
                 where a.attrelid = 'public.learning_dialog_session_contexts'::regclass
                   and a.attnum > 0
                   and not a.attisdropped
                """
            )
            context_columns = {row[0] for row in cur.fetchall()}
            assert {"session_id", "instruction_md", "criteria", "teacher_context_md", "dialog_config"} <= context_columns

            cur.execute(
                """
                select indexdef
                  from pg_indexes
                 where schemaname = 'public'
                   and tablename = 'learning_dialog_sessions'
                """
            )
            indexes = " ".join(str(row[0]) for row in cur.fetchall()).lower()
            assert "where (status = 'active'::text)" in indexes or "where status = 'active'" in indexes


@pytest.mark.anyio
async def test_dialog_submission_reference_and_kind_constraints_exist() -> None:
    _require_db_or_skip()

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select is_nullable
                  from information_schema.columns
                 where table_schema = 'public'
                   and table_name = 'learning_submissions'
                   and column_name = 'dialog_session_id'
                """
            )
            assert (cur.fetchone() or [None])[0] == "YES"

            cur.execute(
                """
                select pg_get_constraintdef(oid)
                  from pg_constraint
                 where conrelid = 'public.learning_submissions'::regclass
                   and conname in ('learning_submissions_kind_check', 'learning_submissions_dialog_kind')
                """
            )
            definitions = " ".join(str(row[0]) for row in cur.fetchall()).lower()
            assert "dialog" in definitions
            assert "dialog_session_id" in definitions


@pytest.mark.anyio
async def test_dialog_hidden_context_has_no_direct_app_role_access() -> None:
    _require_db_or_skip()

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select has_table_privilege('gustav_limited', 'public.learning_dialog_session_contexts', 'select')"
            )
            assert bool((cur.fetchone() or [True])[0]) is False
            cur.execute(
                "select has_table_privilege('gustav_limited', 'public.learning_dialog_session_contexts', 'insert')"
            )
            assert bool((cur.fetchone() or [True])[0]) is False
