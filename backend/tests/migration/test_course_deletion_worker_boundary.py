"""Contract tests for the least-privilege course-deletion worker boundary."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260808120000_course_deletion_worker_boundary.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _worker_dsn() -> str:
    return os.getenv("LEARNING_WORKER_DATABASE_URL") or (
        "postgresql://"
        f"{os.getenv('LEARNING_WORKER_DB_USER', 'gustav_worker')}:"
        f"{os.getenv('LEARNING_WORKER_DB_PASSWORD', 'CHANGE_ME_DEV')}@"
        f"{os.getenv('TEST_DB_HOST', '127.0.0.1')}:"
        f"{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


def _admin_dsn() -> str:
    return os.getenv("TEST_DATABASE_ADMIN_URL") or (
        "postgresql://"
        f"{os.getenv('DB_SUPERUSER', 'postgres')}:"
        f"{os.getenv('DB_SUPERPASSWORD', 'postgres')}@"
        f"{os.getenv('TEST_DB_HOST', '127.0.0.1')}:"
        f"{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


def _app_dsn() -> str:
    return os.getenv("DATABASE_URL") or (
        "postgresql://"
        f"{os.getenv('APP_DB_USER', 'gustav_app')}:"
        f"{os.getenv('APP_DB_PASSWORD', 'CHANGE_ME_DEV')}@"
        f"{os.getenv('TEST_DB_HOST', '127.0.0.1')}:"
        f"{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


def _cleanup_course_fixture(*, course_id: str, job_id: str | None = None) -> None:
    """Remove only UUID-scoped rows created by a lifecycle integration test."""

    import psycopg

    with psycopg.connect(_admin_dsn()) as conn:
        with conn.cursor() as cur:
            if job_id:
                cur.execute(
                    "delete from public.storage_deletion_outbox where deletion_job_id = %s",
                    (job_id,),
                )
                cur.execute(
                    "delete from public.course_deletion_jobs where id = %s",
                    (job_id,),
                )
            cur.execute(
                "update public.courses set status = 'active' where id = %s",
                (course_id,),
            )
            cur.execute("delete from public.courses where id = %s", (course_id,))


def test_worker_lifecycle_uses_narrow_security_definer_commands() -> None:
    sql = _sql()

    for function_name in (
        "learning_worker_claim_course_deletion",
        "learning_worker_complete_storage_deletion",
        "learning_worker_fail_storage_deletion",
        "learning_worker_claim_expired_export",
        "learning_worker_complete_expired_export",
        "learning_worker_fail_expired_export",
    ):
        assert f"function public.{function_name}" in sql
        assert f"grant execute on function public.{function_name}" in sql
    assert "security definer" in sql
    assert "set search_path = pg_catalog, public" in sql
    assert "to gustav_worker" in sql
    assert "bypassrls" not in sql


def test_storage_deletion_claims_have_leases_backoff_and_terminal_failure() -> None:
    sql = _sql()

    assert "lease_token" in sql
    assert "leased_until" in sql
    assert "next_attempt_at" in sql
    assert "status in ('pending', 'processing', 'deleted', 'failed')" in sql
    assert "storage_delete_failed" in sql
    assert "new_retry_count >= 20" in sql


def test_expired_export_cleanup_stops_after_the_terminal_retry_count() -> None:
    sql = _sql()

    assert "e.cleanup_retry_count < 20" in sql


def test_course_deletion_is_idempotent_and_worker_cascades_are_narrowly_allowed() -> None:
    sql = _sql()

    assert "idx_course_deletion_jobs_one_open_per_course" in sql
    assert "queue_course_deletion_owned" in sql
    assert "status = 'deleting'" in sql
    assert "session_user = 'gustav_worker'" in sql
    assert "tg_op = 'delete'" in sql


def test_worker_health_probe_covers_lifecycle_commands_without_claiming_work() -> None:
    sql = _sql()

    assert "lifecycle_commands" in sql
    assert "has_function_privilege" in sql


@pytest.mark.db_write
def test_worker_executes_health_command_without_direct_lifecycle_table_access() -> None:
    """Prove the installed worker role has commands, not broad table access."""

    _require_db_or_skip()
    import psycopg

    with psycopg.connect(_worker_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_user")
            if (cur.fetchone() or [None])[0] != "gustav_worker":
                pytest.skip("dedicated gustav_worker login is not configured")
            cur.execute(
                "select row_security_active('public.course_deletion_jobs'::regclass)"
            )
            assert (cur.fetchone() or [False])[0] is True
            cur.execute("select count(*) from public.course_deletion_jobs")
            assert (cur.fetchone() or [-1])[0] == 0
            cur.execute(
                "select check_name, status from public.learning_worker_health_probe()"
            )
            checks = dict(cur.fetchall())
    assert checks["lifecycle_commands"] == "ok"


@pytest.mark.db_write
def test_storage_claim_is_exclusive_and_expired_lease_can_be_resumed() -> None:
    """Only one worker owns an object until its lease expires."""

    _require_db_or_skip()
    import psycopg

    course_id, job_id, outbox_id = str(uuid4()), str(uuid4()), str(uuid4())
    try:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.courses(
                        id, title, subject, grade_level, school_year_start,
                        teacher_id, status
                    ) values (%s, 'Lease-Test', 'Informatik', '10', 2026, %s, 'deleting')
                    """,
                    (course_id, f"teacher-{course_id}"),
                )
                cur.execute(
                    """
                    insert into public.course_deletion_jobs(
                        id, course_id, owner_sub, course_title, status,
                        started_at
                    ) values (%s, %s, %s, 'Lease-Test', 'processing', now())
                    """,
                    (job_id, course_id, f"teacher-{course_id}"),
                )
                cur.execute(
                    """
                    insert into public.storage_deletion_outbox(
                        id, deletion_job_id, bucket, storage_key, status,
                        lease_token, leased_until
                    ) values (
                        %s, %s, 'submissions', 'tests/lease-object',
                        'processing', %s, now() + interval '90 seconds'
                    )
                    """,
                    (outbox_id, job_id, str(uuid4())),
                )

                cur.execute(
                    "select lease_token from public.storage_deletion_outbox where id = %s",
                    (outbox_id,),
                )
                first_token = (cur.fetchone() or [None])[0]

        with psycopg.connect(_worker_dsn()) as second_worker:
            with second_worker.cursor() as cur:
                cur.execute("select * from public.learning_worker_claim_course_deletion()")
                assert cur.fetchone() is None

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update public.storage_deletion_outbox set leased_until = now() - interval '1 second' where id = %s",
                    (outbox_id,),
                )
                cur.execute("select * from public.learning_worker_claim_course_deletion()")
                resumed_claim = cur.fetchone()
                assert resumed_claim and str(resumed_claim[2]) == outbox_id
                resumed_token = resumed_claim[5]
                assert resumed_token != first_token

        with psycopg.connect(_worker_dsn()) as resumed_worker:
            with resumed_worker.cursor() as cur:
                cur.execute(
                    "select public.learning_worker_complete_storage_deletion(%s, %s)",
                    (outbox_id, first_token),
                )
                assert (cur.fetchone() or [None])[0] is not True
                cur.execute(
                    "select public.learning_worker_complete_storage_deletion(%s, %s)",
                    (outbox_id, resumed_token),
                )
                assert (cur.fetchone() or [None])[0] is True
                cur.execute("select * from public.learning_worker_claim_course_deletion()")
                finalized = cur.fetchone()
                assert finalized and finalized[0] == "finalized"

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("select status from public.course_deletion_jobs where id = %s", (job_id,))
                assert (cur.fetchone() or [None])[0] == "completed"
                cur.execute("select 1 from public.courses where id = %s", (course_id,))
                assert cur.fetchone() is None
    finally:
        _cleanup_course_fixture(course_id=course_id, job_id=job_id)


@pytest.mark.db_write
def test_deleting_course_blocks_app_mutation_while_worker_cascade_succeeds() -> None:
    """The cascade exception is tied to the worker login, not SECURITY DEFINER."""

    _require_db_or_skip()
    import psycopg

    course_id, job_id, outbox_id = str(uuid4()), str(uuid4()), str(uuid4())
    owner_sub = f"teacher-{course_id}"
    lease_token = str(uuid4())
    try:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.courses(
                        id, title, subject, grade_level, school_year_start,
                        teacher_id, status
                    ) values (%s, 'Guard-Test', 'Informatik', '10', 2026, %s, 'active')
                    """,
                    (course_id, owner_sub),
                )
                cur.execute(
                    "insert into public.course_memberships(course_id, student_id) values (%s, %s)",
                    (course_id, f"student-{course_id}"),
                )
                cur.execute(
                    "update public.courses set status = 'deleting' where id = %s",
                    (course_id,),
                )
                cur.execute(
                    """
                    insert into public.course_deletion_jobs(
                        id, course_id, owner_sub, course_title, status
                    ) values (%s, %s, %s, 'Guard-Test', 'processing')
                    """,
                    (job_id, course_id, owner_sub),
                )
                cur.execute(
                    """
                    insert into public.storage_deletion_outbox(
                        id, deletion_job_id, bucket, storage_key, status,
                        lease_token, leased_until
                    ) values (
                        %s, %s, 'submissions', 'tests/guard-object',
                        'processing', %s, now() + interval '90 seconds'
                    )
                    """,
                    (outbox_id, job_id, lease_token),
                )

        with psycopg.connect(_app_dsn()) as app:
            with app.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
                    cur.execute(
                        "delete from public.course_memberships where course_id = %s",
                        (course_id,),
                    )

        with psycopg.connect(_worker_dsn()) as worker:
            with worker.cursor() as cur:
                cur.execute(
                    "select public.learning_worker_complete_storage_deletion(%s, %s)",
                    (outbox_id, lease_token),
                )
                assert (cur.fetchone() or [None])[0] is True
                cur.execute("select * from public.learning_worker_claim_course_deletion()")
                claim = cur.fetchone()
                assert claim and claim[0] == "finalized"

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 from public.courses where id = %s", (course_id,))
                assert cur.fetchone() is None
                cur.execute("select status from public.course_deletion_jobs where id = %s", (job_id,))
                assert (cur.fetchone() or [None])[0] == "completed"
    finally:
        _cleanup_course_fixture(course_id=course_id, job_id=job_id)


@pytest.mark.db_write
def test_terminal_storage_failure_requires_confirmed_retry() -> None:
    """The twentieth failure retains metadata until the owner confirms retry."""

    _require_db_or_skip()
    import psycopg

    course_id, job_id, outbox_id = str(uuid4()), str(uuid4()), str(uuid4())
    owner_sub = f"teacher-{course_id}"
    lease_token = str(uuid4())
    try:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.courses(
                        id, title, subject, grade_level, school_year_start,
                        teacher_id, status
                    ) values (%s, 'Retry-Test', 'Informatik', '10', 2026, %s, 'deleting')
                    """,
                    (course_id, owner_sub),
                )
                cur.execute(
                    """
                    insert into public.course_deletion_jobs(
                        id, course_id, owner_sub, course_title, status, retry_count
                    ) values (%s, %s, %s, 'Retry-Test', 'processing', 19)
                    """,
                    (job_id, course_id, owner_sub),
                )
                cur.execute(
                    """
                    insert into public.storage_deletion_outbox(
                        id, deletion_job_id, bucket, storage_key, status,
                        retry_count, lease_token, leased_until
                    ) values (
                        %s, %s, 'submissions', 'tests/retry-object', 'processing',
                        19, %s, now() + interval '90 seconds'
                    )
                    """,
                    (outbox_id, job_id, lease_token),
                )

        with psycopg.connect(_worker_dsn()) as worker:
            with worker.cursor() as cur:
                cur.execute(
                    "select public.learning_worker_fail_storage_deletion(%s, %s, 'storage_delete_failed')",
                    (outbox_id, lease_token),
                )
                assert (cur.fetchone() or [None])[0] is True

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("select status, retry_count from public.course_deletion_jobs where id = %s", (job_id,))
                assert cur.fetchone() == ("failed", 20)
                cur.execute("select status, retry_count from public.storage_deletion_outbox where id = %s", (outbox_id,))
                assert cur.fetchone() == ("failed", 20)
                cur.execute("select status from public.courses where id = %s", (course_id,))
                assert (cur.fetchone() or [None])[0] == "deleting"

                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                with pytest.raises(psycopg.errors.CheckViolation):
                    cur.execute(
                        "select (public.queue_course_deletion_owned(%s, %s, 'Falsch', true)).id",
                        (course_id, owner_sub),
                    )
                conn.rollback()

                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    "select (public.queue_course_deletion_owned(%s, %s, 'Retry-Test', true)).id::text",
                    (course_id, owner_sub),
                )
                assert (cur.fetchone() or [None])[0] == job_id
                cur.execute("select status, retry_count from public.course_deletion_jobs where id = %s", (job_id,))
                assert cur.fetchone() == ("pending", 0)
                cur.execute("select status, retry_count from public.storage_deletion_outbox where id = %s", (outbox_id,))
                assert cur.fetchone() == ("pending", 0)
    finally:
        _cleanup_course_fixture(course_id=course_id, job_id=job_id)


@pytest.mark.db_write
def test_expired_export_claim_is_leased_and_token_bound() -> None:
    """Expired archive cleanup is resumable and stale acknowledgements are rejected."""

    _require_db_or_skip()
    import psycopg

    course_id, export_id = str(uuid4()), str(uuid4())
    try:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.courses(
                        id, title, subject, grade_level, school_year_start,
                        teacher_id, status
                    ) values (%s, 'Export-Lease-Test', 'Informatik', '10', 2026, %s, 'active')
                    """,
                    (course_id, f"teacher-{course_id}"),
                )
                first_token = str(uuid4())
                cur.execute(
                    """
                    insert into public.learning_export_jobs(
                        id, course_id, student_sub, status, storage_key,
                        size_bytes, expires_at, cleanup_lease_token,
                        cleanup_leased_until
                    ) values (
                        %s, %s, %s, 'ready', 'exports/test.zip', 10,
                        now() - interval '1 minute', %s,
                        now() + interval '90 seconds'
                    )
                    """,
                    (export_id, course_id, f"student-{course_id}", first_token),
                )

        with psycopg.connect(_worker_dsn()) as worker:
            with worker.cursor() as cur:
                cur.execute("select * from public.learning_worker_claim_expired_export()")
                assert cur.fetchone() is None

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update public.learning_export_jobs set cleanup_leased_until = now() - interval '1 second' where id = %s",
                    (export_id,),
                )
                cur.execute("select * from public.learning_worker_claim_expired_export()")
                resumed_claim = cur.fetchone()
                assert resumed_claim and str(resumed_claim[0]) == export_id
                resumed_token = resumed_claim[2]
                assert str(resumed_token) != first_token

        with psycopg.connect(_worker_dsn()) as worker:
            with worker.cursor() as cur:
                cur.execute(
                    "select public.learning_worker_complete_expired_export(%s, %s)",
                    (export_id, first_token),
                )
                assert (cur.fetchone() or [None])[0] is not True
                cur.execute(
                    "select public.learning_worker_complete_expired_export(%s, %s)",
                    (export_id, resumed_token),
                )
                assert (cur.fetchone() or [None])[0] is True

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select status, storage_key from public.learning_export_jobs where id = %s",
                    (export_id,),
                )
                assert cur.fetchone() == ("expired", None)
    finally:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("delete from public.learning_export_jobs where id = %s", (export_id,))
        _cleanup_course_fixture(course_id=course_id)
