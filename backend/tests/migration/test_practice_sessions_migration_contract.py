"""Static schema contract for practice state, sessions and attempts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260808150000_practice_sessions.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_practice_tables_precision_rls_and_limits_exist() -> None:
    sql = _sql()
    for table in (
        "learning_practice_states",
        "learning_practice_sessions",
        "learning_practice_session_stacks",
        "learning_practice_session_items",
        "learning_practice_attempts",
    ):
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
    assert "stability_days double precision" in sql
    assert "interval_seconds bigint" in sql
    assert "completion_token_hash bytea" in sql
    assert "where status = 'active'" in sql
    assert "presentation_number" in sql
    assert "scheduler_applied_at" in sql
    assert "set search_path = public, pg_temp" in sql


def test_modular_state_source_is_extended_for_practice_due_counts() -> None:
    sql = _sql()
    assert "get_modular_unit_module_states_for_student" in sql
    assert "p_include_practice boolean" in sql
    assert "module_kind text" in sql
    assert "due_tasks_count integer" in sql

