"""Migration contract for secure course invitations and mail delivery."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20260815120000_course_invitations.sql"
RETRY_HARDENING_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815214500_course_invitation_mail_retry_hardening.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_course_invitation_migration_defines_all_private_tables() -> None:
    sql = _sql()
    for table in [
        "course_invitations",
        "course_invite_redemptions",
        "course_invite_mail_batches",
        "course_invite_mail_deliveries",
    ]:
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_course_invitation_migration_enforces_one_active_link_and_atomic_redemption() -> None:
    sql = _sql()
    assert "course_invitations_one_unrevoked_per_course" in sql
    assert "where revoked_at is null" in sql
    assert "create_course_invitation" in sql
    assert "redeem_course_invitation" in sql
    assert "for update" in sql
    assert "invite_already_used_membership_removed" in sql
    assert "on conflict (invitation_id, student_sub)" in sql


def test_course_invitation_migration_uses_least_privilege_worker_functions() -> None:
    sql = _sql()
    assert "claim_course_invite_mail_delivery" in sql
    assert "complete_course_invite_mail_delivery" in sql
    assert "fail_course_invite_mail_delivery" in sql
    assert "purge_course_invite_mail_recipients" in sql
    assert "grant execute on function public.claim_course_invite_mail_delivery" in sql
    assert "revoke all on table public.course_invite_mail_deliveries from public" in sql


def test_course_archiving_revokes_invitation_without_restore_reactivation() -> None:
    sql = _sql()
    assert "revoke_course_invitation_on_course_archive" in sql
    assert "new.status <> 'active'" in sql
    assert "old.status = 'active'" in sql


def test_redemption_conflict_target_is_unambiguous() -> None:
    fix_sql = (
        ROOT / "supabase/migrations/20260815121000_course_invitation_redeem_conflict_fix.sql"
    ).read_text(encoding="utf-8").lower()
    assert "on conflict on constraint course_memberships_pkey" in fix_sql


def test_mail_retry_hardening_distinguishes_transient_from_permanent_failures() -> None:
    sql = RETRY_HARDENING_MIGRATION.read_text(encoding="utf-8").lower()

    assert "add column retryable boolean" in sql
    assert "d.retryable" in sql
    assert "d.retry_count < 5" in sql
    assert "p_retryable and invite_valid" in sql
    assert "set status = 'failed'" in sql
    assert "retryable = false" in sql
    assert "return -1" in sql
