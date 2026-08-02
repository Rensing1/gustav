"""Static migration contract checks that run even without local Postgres."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260801120000_dialog_tasks.sql"
).read_text(encoding="utf-8").lower()


def test_dialog_snapshot_and_starter_provenance_are_explicit() -> None:
    assert "create table if not exists public.learning_dialog_session_contexts" in MIGRATION
    assert "max_attempts integer null" in MIGRATION
    assert "used_sentence_starter_source" in MIGRATION
    assert "learning_dialog_turn_student_content_immutable" in MIGRATION


def test_safe_projection_and_teacher_transcript_use_security_definer_functions() -> None:
    assert "function public.learning_get_visible_dialog_configs" in MIGRATION
    assert "function public.teaching_get_dialog_submission" in MIGRATION
    assert MIGRATION.count("security definer") >= 4
    assert "revoke all on public.learning_dialog_session_contexts from public, gustav_limited" in MIGRATION


def test_usage_events_are_content_free_and_rls_scoped() -> None:
    assert "create table if not exists public.dialog_ai_usage_events" in MIGRATION
    assert "dialog_ai_usage_events_insert_scoped" in MIGRATION
    assert "error_code text null" in MIGRATION
    for forbidden_content_column in ("prompt_md", "response_md", "student_message_md"):
        table_body = MIGRATION.split("create table if not exists public.dialog_ai_usage_events", 1)[1].split(");", 1)[0]
        assert forbidden_content_column not in table_body


def test_dialog_completion_reference_is_unique() -> None:
    assert "idx_learning_submissions_dialog_session" in MIGRATION
    assert "where dialog_session_id is not null" in MIGRATION


def test_attempt_limit_counts_only_final_dialog_submissions() -> None:
    assert "and intent = 'submit'\n     and kind = 'dialog'" in MIGRATION
