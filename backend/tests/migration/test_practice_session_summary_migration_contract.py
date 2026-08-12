"""Static schema contract for durable practice-session summaries."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260812124000_practice_session_summary.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_practice_summary_snapshot_fields_and_end_reason_are_constrained() -> None:
    sql = _sql()

    assert "add column module_title text" in sql
    assert "add column end_reason text" in sql
    assert "completed" in sql
    assert "stopped" in sql
    assert "empty" in sql
    assert "validate constraint learning_practice_sessions_end_reason_check" in sql
    assert "set search_path = public, pg_temp" in sql
