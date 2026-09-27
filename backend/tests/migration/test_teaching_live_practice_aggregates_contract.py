"""Security and batching contract for the teacher Live practice helper."""

from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "20260927120000_teaching_live_practice_aggregates.sql"


def test_live_practice_helper_is_owner_scoped_and_bulk() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "get_unit_live_practice_aggregates_for_owner" in sql
    assert "security definer" in sql
    assert "set search_path = pg_catalog, public" in sql
    assert "current_setting('app.current_sub'" in sql
    assert "course_memberships" in sql
    assert "course_modules" in sql
    assert "p_student_subs text[]" in sql
    assert "get_modular_unit_module_states_for_student" in sql
    assert "revoke all on function" in sql
    assert "grant execute on function" in sql
