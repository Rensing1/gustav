"""
Provisioning test for Supabase Storage buckets.

Why:
    We want deterministic, versioned provisioning of required buckets via
    SQL migrations (not runtime side-effects), ensuring both `materials` and
    `submissions` exist and are private (`public=false`).

Behavior (BDD):
    Given a reachable database with the storage schema,
    When all migrations have been applied,
    Then the `materials` and `submissions` buckets exist in storage.buckets
    And both have public=false.

Notes:
    - Skips if DB unreachable or storage schema is not present (e.g., tests on
      minimal Postgres without Supabase extensions).
    - This test should fail before adding the migration for `submissions`.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest


pytestmark = pytest.mark.db_write


def _probe(dsn: str) -> bool:
    try:
        import psycopg  # type: ignore
        with psycopg.connect(dsn, connect_timeout=5):
            return True
    except Exception:
        return False


@pytest.mark.anyio
async def test_buckets_materials_and_submissions_exist_and_private():
    dsn = (
        os.getenv("RLS_TEST_DSN")
        or os.getenv("DATABASE_URL")
        or ""
    )
    if not dsn or not _probe(dsn):
        pytest.skip("DB unreachable or no DSN configured for storage buckets check")

    import psycopg  # type: ignore

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Check storage schema existence first
            cur.execute(
                """
                select count(*)
                from information_schema.tables
                where table_schema='storage' and table_name='buckets'
                """
            )
            cnt = cur.fetchone()[0]
            if cnt == 0:
                pytest.skip("storage.buckets not available in this DB")

            cur.execute(
                """
                select id, name, public
                from storage.buckets
                where id in ('materials','submissions')
                order by id
                """
            )
            rows = cur.fetchall()
            got = {r[0]: bool(r[2]) for r in rows}
            # materials must exist and be private
            assert "materials" in got, "materials bucket must be provisioned via migration"
            assert got["materials"] is False, "materials bucket must be private (public=false)"
            # submissions must exist and be private
            assert "submissions" in got, "submissions bucket must be provisioned via migration"
            assert got["submissions"] is False, "submissions bucket must be private (public=false)"

            # Scratch SB3 uploads require this MIME to be accepted by the bucket.
            cur.execute(
                """
                select count(*)
                from information_schema.columns
                where table_schema='storage' and table_name='buckets' and column_name='allowed_mime_types'
                """
            )
            has_allowlist = int(cur.fetchone()[0]) > 0
            if not has_allowlist:
                pytest.skip("storage.buckets.allowed_mime_types not available in this DB")

            cur.execute("select allowed_mime_types from storage.buckets where id='submissions'")
            row = cur.fetchone()
            assert row, "submissions bucket row must exist"
            allowed = row[0]
            assert allowed, "submissions bucket must define allowed_mime_types"
            assert "application/x.scratch.sb3" in allowed, "submissions bucket must accept application/x.scratch.sb3"
            assert "application/x.makecode.hex" in allowed, "submissions bucket must accept application/x.makecode.hex"
            assert "application/x.filius.fls" in allowed, "submissions bucket must accept application/x.filius.fls"


def test_sb3_storage_migration_updates_allowlist_additively() -> None:
    """The SB3 migration must preserve existing MIME entries instead of replacing them."""
    migration = Path("supabase/migrations/20260219193000_storage_submissions_bucket_allow_sb3.sql")
    sql = migration.read_text(encoding="utf-8").lower()

    assert "coalesce(allowed_mime_types" in sql
    assert "unnest(" in sql
    assert "application/x.scratch.sb3" in sql


def test_local_supabase_config_allows_makecode_hex_in_submissions_bucket() -> None:
    """Local Supabase bucket bootstrap must allow MakeCode HEX and Filius FLS uploads."""
    config = Path("supabase/config.toml").read_text(encoding="utf-8")

    submissions_section = config.split("[storage.buckets.submissions]", maxsplit=1)[1]
    submissions_section = submissions_section.split("\n[", maxsplit=1)[0]

    assert "application/x.makecode.hex" in submissions_section
    assert "application/x.filius.fls" in submissions_section


def test_filius_storage_migration_updates_allowlist_additively() -> None:
    """The Filius migration must preserve existing MIME entries instead of replacing them."""
    migration = Path("supabase/migrations/20260507120000_storage_submissions_bucket_allow_filius_fls.sql")
    sql = migration.read_text(encoding="utf-8").lower()

    assert "coalesce(allowed_mime_types" in sql
    assert "unnest(" in sql
    assert "application/x.filius.fls" in sql


def test_filius_storage_migration_updates_all_supported_submission_buckets() -> None:
    """Both canonical and legacy learning submission buckets must accept FLS uploads."""
    migration = Path("supabase/migrations/20260507120000_storage_submissions_bucket_allow_filius_fls.sql")
    sql = migration.read_text(encoding="utf-8").lower()

    assert "'submissions'" in sql
    assert "'learning-submissions'" in sql
    assert "where id in" in sql
    assert "application/x.filius.fls" in sql
