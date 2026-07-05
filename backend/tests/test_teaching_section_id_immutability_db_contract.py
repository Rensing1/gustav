"""
DB contract: task/material section_id must remain immutable.

Why:
    Two open PR-fix items rely on this invariant:
    - `learning_submissions.section_id` must not drift due to task moves.
    - `unit_sections.tasks_total/materials_count` must not go stale because
      cross-section moves are disallowed at DB level.
"""

from __future__ import annotations

import os

import pytest


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


def _pick_dsn() -> str:
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("RLS_TEST_DSN")
        or os.getenv("TEACHING_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


def _require_db_or_skip() -> None:
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")
    try:
        with psycopg.connect(_pick_dsn(), connect_timeout=5):
            return
    except Exception:
        pytest.skip("Database not reachable for DB constraint tests")


@pytest.mark.anyio
async def test_unit_tasks_section_id_is_immutable() -> None:
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DBTeachingRepo unavailable")

    import psycopg  # type: ignore

    repo = DBTeachingRepo()
    owner = "teacher-task-section-immutability"
    unit = repo.create_unit(title="Unit", summary=None, author_id=owner)
    sec_a = repo.create_section(unit_id=unit["id"], title="A", author_id=owner)
    sec_b = repo.create_section(unit_id=unit["id"], title="B", author_id=owner)
    task = repo.create_task(
        unit_id=unit["id"],
        section_id=sec_a["id"],
        author_id=owner,
        instruction_md="Aufgabe",
        criteria=[],
        teacher_context_md=None,
        due_at=None,
        max_attempts=None,
        kind="native",
        h5p_content_id=None,
        h5p_display_options={},
    )

    with psycopg.connect(_pick_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner,))
            with pytest.raises(Exception) as excinfo:
                cur.execute(
                    """
                    update public.unit_tasks
                       set section_id = %s::uuid
                     where id = %s::uuid
                    """,
                    (sec_b["id"], task["id"]),
                )
            assert getattr(excinfo.value, "sqlstate", None) == "23514"
            conn.rollback()
            cur.execute("select set_config('app.current_sub', %s, true)", (owner,))

            cur.execute("select section_id::text from public.unit_tasks where id = %s::uuid", (task["id"],))
            row = cur.fetchone()
            assert row and row[0] == sec_a["id"]


@pytest.mark.anyio
async def test_unit_materials_section_id_is_immutable() -> None:
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DBTeachingRepo unavailable")

    import psycopg  # type: ignore

    repo = DBTeachingRepo()
    owner = "teacher-material-section-immutability"
    unit = repo.create_unit(title="Unit", summary=None, author_id=owner)
    sec_a = repo.create_section(unit_id=unit["id"], title="A", author_id=owner)
    sec_b = repo.create_section(unit_id=unit["id"], title="B", author_id=owner)
    material = repo.create_markdown_material(
        unit_id=unit["id"],
        section_id=sec_a["id"],
        author_id=owner,
        title="Material",
        body_md="Inhalt",
    )

    with psycopg.connect(_pick_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner,))
            with pytest.raises(Exception) as excinfo:
                cur.execute(
                    """
                    update public.unit_materials
                       set section_id = %s::uuid
                     where id = %s::uuid
                    """,
                    (sec_b["id"], material["id"]),
                )
            assert getattr(excinfo.value, "sqlstate", None) == "23514"
            conn.rollback()
            cur.execute("select set_config('app.current_sub', %s, true)", (owner,))

            cur.execute(
                "select section_id::text from public.unit_materials where id = %s::uuid",
                (material["id"],),
            )
            row = cur.fetchone()
            assert row and row[0] == sec_a["id"]
