"""Source contract for practice metadata in the learner graph."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend" / "learning" / "repo_modular_unit_queries.py"


def test_graph_uses_extended_canonical_state_query_and_exposes_safe_fields() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "get_modular_unit_module_states_for_student(%s, %s::uuid, %s::uuid, true)" in source
    assert '"module_kind"' in source
    assert '"due_tasks_count"' in source
    assert "teacher_context_md" not in source
    assert "model_solution_md" not in source
