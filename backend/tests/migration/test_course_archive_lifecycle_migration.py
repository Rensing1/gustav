from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260806120000_course_archive_lifecycle.sql"
WORKER_MIGRATION = ROOT / "supabase" / "migrations" / "20260806130000_course_archive_worker_functions.sql"
WRITE_GUARD_MIGRATION = ROOT / "supabase" / "migrations" / "20260806131000_archived_course_learning_write_guards.sql"
ROSTER_MIGRATION = ROOT / "supabase" / "migrations" / "20260806132000_course_roster_lifecycle_projection.sql"
MUTATION_GUARD_MIGRATION = ROOT / "supabase" / "migrations" / "20260806124500_course_mutation_guards.sql"
ACTIVE_ACCESS_MIGRATION = ROOT / "supabase" / "migrations" / "20260806135000_active_learning_access_helpers.sql"
MEMBERSHIP_REACTIVATION_MIGRATION = ROOT / "supabase" / "migrations" / "20260806140000_course_membership_reactivation_policy.sql"
WORKER_ARCHIVE_COMPLETION_MIGRATION = ROOT / "supabase" / "migrations" / "20260806141000_archived_course_worker_completion.sql"
EXPORT_BUCKET_MIGRATION = ROOT / "supabase" / "migrations" / "20260806142000_learning_exports_storage_bucket.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_course_archive_migration_defines_lifecycle_and_history_tables() -> None:
    sql = _sql()

    assert "school_year_start" in sql
    assert "archived_at" in sql
    assert "ended_at" in sql
    assert "course_archive_snapshots" in sql
    assert "learning_submission_task_snapshots" in sql
    assert "learning_export_jobs" in sql
    assert "course_deletion_jobs" in sql
    assert "storage_deletion_outbox" in sql


def test_course_archive_migration_guards_private_history_with_rls() -> None:
    sql = _sql()

    assert "alter table public.learning_export_jobs enable row level security" in sql
    assert "alter table public.course_archive_snapshots enable row level security" in sql
    assert "app.current_sub" in sql
    assert "status in ('active', 'archived', 'deleting')" in sql


def test_course_archive_worker_uses_explicit_least_privilege_functions() -> None:
    sql = WORKER_MIGRATION.read_text(encoding="utf-8").lower()

    assert "learning_worker_claim_export" in sql
    assert "learning_worker_export_snapshot" in sql
    assert "grant execute on function public.learning_worker_complete_export" in sql
    assert "select result.id, 'submissions', e.storage_key" in sql


def test_archived_courses_reject_new_learning_but_keep_task_history() -> None:
    sql = WRITE_GUARD_MIGRATION.read_text(encoding="utf-8").lower()

    assert "guard_active_course_learning_write" in sql
    assert "trg_learning_submissions_active_course" in sql
    assert "trg_dialog_turns_active_course" in sql
    assert "current_user = 'gustav_worker'" in sql
    assert "on delete restrict" in sql


def test_archived_roster_preserves_former_members_without_polluting_active_roster() -> None:
    sql = ROSTER_MIGRATION.read_text(encoding="utf-8").lower()
    assert "c.status = 'archived' or m.ended_at is null" in sql


def test_release_mutation_guard_uses_historical_course_module_column() -> None:
    sql = MUTATION_GUARD_MIGRATION.read_text(encoding="utf-8").lower()
    assert "new.course_module_id" in sql


def test_active_learning_helpers_exclude_archived_and_former_members() -> None:
    sql = ACTIVE_ACCESS_MIGRATION.read_text(encoding="utf-8").lower()
    assert "security definer" in sql
    assert "cm.ended_at is null" in sql
    assert "c.status = 'active'" in sql
    assert "r.course_module_id" in sql


def test_membership_reactivation_remains_owner_only() -> None:
    sql = MEMBERSHIP_REACTIVATION_MIGRATION.read_text(encoding="utf-8").lower()
    assert "for update to gustav_limited" in sql
    assert "course_exists_for_owner" in sql


def test_archived_course_guard_recognizes_the_worker_session_behind_definer_functions() -> None:
    sql = WORKER_ARCHIVE_COMPLETION_MIGRATION.read_text(encoding="utf-8").lower()
    assert "session_user = 'gustav_worker'" in sql
    assert "current_user = 'gustav_worker'" not in sql


def test_exports_use_a_private_zip_enabled_bucket_and_matching_delete_outbox() -> None:
    sql = EXPORT_BUCKET_MIGRATION.read_text(encoding="utf-8").lower()
    assert "'learning-exports'" in sql
    assert "'application/zip'" in sql
    assert "select result.id, 'learning-exports', e.storage_key" in sql
