"""Contract checks for worker-scoped practice completion helpers."""

from pathlib import Path


MIGRATION = Path("supabase/migrations/20260808170000_practice_completion_helpers.sql")


def test_worker_helpers_are_hardened_and_narrowly_granted() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for name in (
        "learning_worker_get_practice_attempt_context",
        "learning_worker_complete_practice_attempt",
        "learning_worker_fail_practice_attempt",
    ):
        assert f"function public.{name}" in sql
        assert f"grant execute on function public.{name}" in sql
    assert "security definer" in sql
    assert "set search_path = public, pg_temp" in sql
    assert "for update" in sql


def test_completion_is_idempotent_and_updates_state_with_attempt_audit() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "scheduler_applied_at" in sql
    assert "on conflict (course_id, student_sub, task_id)" in sql
    assert "status = 'pending'" in sql
    assert "support_pending" in sql
