"""Migration contract for download-only program and OpenDocument materials."""

import os
from pathlib import Path

import pytest

from backend.tests.utils.db import require_db_or_skip

MIGRATION = Path(
    "supabase/migrations/20261004132950_teaching_material_program_files.sql"
)


def test_migration_keeps_material_bucket_private_and_adds_every_mime() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "public = false" in sql
    assert "coalesce(allowed_mime_types" in sql
    for mime_type in (
        "application/x.scratch.sb3",
        "application/x.makecode.hex",
        "application/x.filius.fls",
        "text/x-python",
        "application/json",
        "text/plain",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
    ):
        assert mime_type in sql


@pytest.mark.db_read
def test_applied_material_bucket_is_private_and_accepts_every_new_mime() -> None:
    require_db_or_skip()
    import psycopg

    dsn = os.getenv("DATABASE_URL") or (
        "postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"
    )
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select allowed_mime_types, public from storage.buckets where id='materials'"
            )
            row = cursor.fetchone()

    assert row is not None
    allowed_mime_types, is_public = row
    assert is_public is False
    assert {
        "application/x.scratch.sb3",
        "application/x.makecode.hex",
        "application/x.filius.fls",
        "text/x-python",
        "application/json",
        "text/plain",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
    } <= set(allowed_mime_types or [])
