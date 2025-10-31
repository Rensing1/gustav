"""
Learning RLS (student): verify policies for released content.

Scenarios:
- Member students can select only rows tied to their released sections.
- Non-members (or missing identity) see no rows, protecting other courses.
"""
from __future__ import annotations

import os
import uuid

import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


def _limited_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _prep_rows(cur, teacher_sub: str, *, course_suffix: str) -> dict[str, str]:
    """Seed one released section with material+task and return identifiers."""
    cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
    cur.execute(
        "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
        (f"RLS Learning {course_suffix}", teacher_sub),
    )
    course_id = cur.fetchone()[0]
    cur.execute(
        "insert into public.units (title, author_id) values (%s, %s) returning id",
        (f"Unit {course_suffix}", teacher_sub),
    )
    unit_id = cur.fetchone()[0]
    cur.execute(
        "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
        (unit_id, f"Section {course_suffix}", 1),
    )
    section_id = cur.fetchone()[0]
    cur.execute(
        "insert into public.course_modules (course_id, unit_id, position) values (%s, %s, %s) returning id",
        (course_id, unit_id, 1),
    )
    module_id = cur.fetchone()[0]
    cur.execute(
        """
        insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by)
        values (%s, %s, true, now(), %s)
        on conflict (course_module_id, section_id)
        do update set visible = excluded.visible, released_at = excluded.released_at, released_by = excluded.released_by
        """,
        (module_id, section_id, teacher_sub),
    )
    cur.execute(
        """
        insert into public.unit_materials (unit_id, section_id, title, body_md, position)
        values (%s, %s, %s, %s, %s)
        returning id
        """,
        (unit_id, section_id, f"Material {course_suffix}", "# Body", 1),
    )
    material_id = cur.fetchone()[0]
    cur.execute(
        """
        insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, hints_md, position)
        values (%s, %s, %s, %s, %s, %s)
        returning id
        """,
        (unit_id, section_id, "Solve the task", ["criterion"], None, 1),
    )
    task_id = cur.fetchone()[0]
    return {
        "course_id": str(course_id),
        "unit_id": str(unit_id),
        "section_id": str(section_id),
        "module_id": str(module_id),
        "material_id": str(material_id),
        "task_id": str(task_id),
    }


@pytest.mark.anyio
async def test_student_rls_policies_show_only_member_rows():
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - defensive for environments without psycopg
        pytest.skip("psycopg not available")

    dsn = _limited_dsn()
    teacher = f"teacher-rls-{uuid.uuid4()}"
    teacher_other = f"teacher-rls-{uuid.uuid4()}"
    student = f"student-rls-{uuid.uuid4()}"
    outsider = f"student-rls-{uuid.uuid4()}"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            ids = _prep_rows(cur, teacher, course_suffix="primary")
            _ = _prep_rows(cur, teacher_other, course_suffix="secondary")
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher,))
            cur.execute("insert into public.course_memberships (course_id, student_id) values (%s, %s)", (ids["course_id"], student))
            conn.commit()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student,))

            cur.execute("select id::text from public.course_modules order by id")
            modules = {row[0] for row in cur.fetchall()}
            assert modules == {ids["module_id"]}

            cur.execute("select id::text from public.units order by id")
            units = {row[0] for row in cur.fetchall()}
            assert units == {ids["unit_id"]}

            cur.execute("select id::text from public.unit_sections order by id")
            sections = {row[0] for row in cur.fetchall()}
            assert sections == {ids["section_id"]}

            cur.execute("select course_module_id::text, section_id::text from public.module_section_releases order by section_id")
            releases = {(row[0], row[1]) for row in cur.fetchall()}
            assert releases == {(ids["module_id"], ids["section_id"])}

            cur.execute("select id::text from public.unit_materials order by id")
            materials = {row[0] for row in cur.fetchall()}
            assert materials == {ids["material_id"]}

            cur.execute("select id::text from public.unit_tasks order by id")
            tasks = {row[0] for row in cur.fetchall()}
            assert tasks == {ids["task_id"]}

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (outsider,))
            cur.execute("select count(*) from public.course_modules")
            assert cur.fetchone()[0] == 0
            cur.execute("select count(*) from public.unit_materials")
            assert cur.fetchone()[0] == 0

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # No identity set -> policies fall back to empty string, hiding rows
            cur.execute("select count(*) from public.course_modules")
            assert cur.fetchone()[0] == 0
