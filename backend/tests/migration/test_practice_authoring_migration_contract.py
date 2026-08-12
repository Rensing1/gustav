"""Static migration contract for practice authoring invariants."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = (
    ROOT / "supabase" / "migrations" / "20260812120000_practice_authoring.sql",
    ROOT / "supabase" / "migrations" / "20260812121000_practice_module_existing_content_guard.sql",
)


def _sql() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS).lower()


def test_practice_authoring_columns_and_immutable_kind_are_migrated() -> None:
    sql = _sql()
    assert "add column if not exists module_kind" in sql
    assert "module_kind in ('learning', 'practice')" in sql
    assert "add column if not exists model_solution_md" in sql
    assert "module_kind is immutable" in sql


def test_practice_graph_and_content_invariants_are_database_enforced() -> None:
    sql = _sql()
    assert "practice_module_outgoing_edge" in sql
    assert "practice_module_material_forbidden" in sql
    assert "practice_task_kind_not_supported" in sql
    assert "practice_fields_required" in sql
    assert "practice_schedule_fields_forbidden" in sql
    assert "practice_module_existing_content_invalid" in sql
    assert "set search_path = public, pg_temp" in sql
