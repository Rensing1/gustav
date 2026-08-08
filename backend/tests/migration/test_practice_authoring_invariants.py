"""Live PostgreSQL tests for practice-authoring invariants.

Why:
    Every authoring path eventually reaches PostgreSQL. These tests prove that
    API, CLI or future imports cannot bypass the practice-module rules.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402


pytestmark = pytest.mark.db_write


def _admin_dsn() -> str:
    return os.getenv("TEST_DATABASE_ADMIN_URL") or (
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )


def _expect_check_violation(conn, cur, sql: str, params: tuple[object, ...]) -> None:  # noqa: ANN001
    """Run one rejected statement inside a savepoint so the fixture survives."""

    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            cur.execute(sql, params)


def test_practice_module_guards_reject_invalid_content_and_graph_edges() -> None:
    require_db_or_skip()

    with psycopg.connect(_admin_dsn()) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into public.units (title, author_id, unit_type) values (%s, %s, 'modular') returning id",
                    ("Practice invariant test", "practice-invariant-test"),
                )
                unit_id = cur.fetchone()[0]
                cur.execute(
                    "insert into public.unit_phases (unit_id, title, position) values (%s, 'Start', 1), (%s, 'Ende', 2) returning id",
                    (unit_id, unit_id),
                )
                phase_one, phase_two = (row[0] for row in cur.fetchall())
                cur.execute(
                    "insert into public.unit_sections (unit_id, title, position) values (%s, 'Üben', 1), (%s, 'Lernen', 2), (%s, 'Altbestand', 3) returning id",
                    (unit_id, unit_id, unit_id),
                )
                practice_section, learning_section, legacy_section = (row[0] for row in cur.fetchall())
                cur.execute(
                    "insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase, module_kind) values (%s, %s, %s, 1, 'practice') returning id",
                    (unit_id, practice_section, phase_one),
                )
                practice_module = cur.fetchone()[0]
                cur.execute(
                    "insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase) values (%s, %s, %s, 1) returning id",
                    (unit_id, learning_section, phase_two),
                )
                learning_module = cur.fetchone()[0]

                cur.execute(
                    "insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, teacher_context_md, model_solution_md, position) values (%s, %s, 'Erkläre.', array['Korrekt'], 'Kontext', 'Lösung', 1)",
                    (unit_id, practice_section),
                )

                _expect_check_violation(
                    conn,
                    cur,
                    "update public.unit_modules set module_kind = 'learning' where id = %s",
                    (practice_module,),
                )
                _expect_check_violation(
                    conn,
                    cur,
                    "insert into public.unit_materials (unit_id, section_id, title, body_md, position) values (%s, %s, 'Material', 'Text', 1)",
                    (unit_id, practice_section),
                )
                _expect_check_violation(
                    conn,
                    cur,
                    "insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position, due_at) values (%s, %s, 'Später', array['Korrekt'], 2, now())",
                    (unit_id, practice_section),
                )
                _expect_check_violation(
                    conn,
                    cur,
                    "insert into public.unit_module_edges (unit_id, from_module_id, to_module_id) values (%s, %s, %s)",
                    (unit_id, practice_module, learning_module),
                )

                cur.execute(
                    "insert into public.unit_materials (unit_id, section_id, title, body_md, position) values (%s, %s, 'Alt', 'Text', 1)",
                    (unit_id, legacy_section),
                )
                _expect_check_violation(
                    conn,
                    cur,
                    "insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase, module_kind) values (%s, %s, %s, 2, 'practice')",
                    (unit_id, legacy_section, phase_two),
                )
        finally:
            conn.rollback()
