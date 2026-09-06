"""Local PostgreSQL integration test for printable-unit batch reads and RLS."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.teaching.printouts import list_printable_content

pytestmark = pytest.mark.db_write


def _dsn() -> str:
    return os.getenv("RLS_TEST_DSN") or os.getenv("TEACHING_DATABASE_URL") or os.getenv("DATABASE_URL") or (
        f"postgresql://{os.getenv('APP_DB_USER', 'gustav_app')}:{os.getenv('APP_DB_PASSWORD', 'CHANGE_ME_DEV')}"
        f"@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


def test_printable_snapshot_batches_owned_materials_and_tasks_in_real_database() -> None:
    try:
        import psycopg

        from backend.teaching.repo_db import DBTeachingRepo

        with psycopg.connect(_dsn(), connect_timeout=5):
            pass
    except Exception as exc:
        pytest.skip(f"Lokale Testdatenbank nicht erreichbar: {exc}")

    repo = DBTeachingRepo(dsn=_dsn())
    author_id = f"print-author-{uuid4()}"
    other_id = f"print-other-{uuid4()}"
    unit = repo.create_unit(title="DB Druckfassung", summary=None, author_id=author_id, unit_type="linear")
    try:
        section = repo.create_section(unit["id"], "Einstieg", author_id)
        material = repo.create_markdown_material(
            unit["id"],
            section["id"],
            author_id,
            title="DB Merkblatt",
            body_md="Nur autorisierter Inhalt.",
        )
        task = repo.create_task(
            unit["id"],
            section["id"],
            author_id,
            instruction_md="Erkläre den Inhalt.",
            criteria=["intern"],
            teacher_context_md="nicht drucken",
            model_solution_md="nicht drucken",
            due_at=None,
            max_attempts=None,
            kind="native",
            h5p_content_id=None,
            h5p_display_options={},
        )

        snapshot = list_printable_content(repo, unit_id=unit["id"], author_id=author_id)

        assert snapshot is not None
        assert snapshot["linear_sections"][0]["materials"][0]["id"] == material["id"]  # type: ignore[index]
        assert snapshot["linear_sections"][0]["tasks"][0]["id"] == task["id"]  # type: ignore[index]
        assert repo.list_materials_for_unit_owned(unit["id"], other_id) == []
        assert repo.list_tasks_for_unit_owned(unit["id"], other_id) == []
    finally:
        repo.delete_unit_owned(unit["id"], author_id)
