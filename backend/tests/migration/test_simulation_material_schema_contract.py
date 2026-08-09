"""Migration contract for interactive simulation materials."""

from pathlib import Path

import os
import pytest

from backend.tests.utils.db import require_db_or_skip


MIGRATION = Path("supabase/migrations/20260808180000_interactive_simulation_materials.sql")


def test_migration_adds_simulation_kind_intent_discriminator_and_offline_mime() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "kind in ('markdown', 'file', 'simulation')" in sql
    assert "material_kind text not null default 'file'" in sql
    assert "material_kind in ('file', 'simulation')" in sql
    assert "mime_type = 'text/html'" in sql
    assert "filename_original" in sql and "%.html" in sql
    assert "application/pdf" in sql
    assert "text/html" in sql
    assert "coalesce(allowed_mime_types" in sql


def test_migration_adds_hardened_batch_asset_visibility_helper() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "get_material_asset_metadata_batch_for_student" in sql
    assert "security invoker" in sql
    assert "set search_path = pg_catalog, public" in sql
    assert "m.kind in ('file', 'simulation')" in sql
    assert "revoke all on function" in sql
    assert "grant execute on function" in sql


@pytest.mark.db_read
def test_applied_database_exposes_simulation_constraints_and_visibility_helper() -> None:
    require_db_or_skip()
    import psycopg

    dsn = os.getenv("DATABASE_URL") or "postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select column_default
                  from information_schema.columns
                 where table_schema='public' and table_name='upload_intents' and column_name='material_kind'
                """
            )
            assert "file" in str((cur.fetchone() or [""])[0])

            cur.execute(
                """
                select pg_get_constraintdef(oid)
                  from pg_constraint
                 where conname='unit_materials_kind_check'
                """
            )
            assert "simulation" in str((cur.fetchone() or [""])[0])

            cur.execute(
                """
                select prosecdef, proconfig
                  from pg_proc
                 where oid = 'public.get_material_asset_metadata_batch_for_student(text,uuid,uuid[])'::regprocedure
                """
            )
            row = cur.fetchone()
            assert row and row[0] is False
            assert "search_path=pg_catalog, public" in list(row[1] or [])

            cur.execute("select allowed_mime_types, public from storage.buckets where id='materials'")
            bucket = cur.fetchone()
            assert bucket and "text/html" in bucket[0]
            assert bucket[1] is False
