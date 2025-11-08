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
import pytest


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

