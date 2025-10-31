"""
Learning repository semantics: membership and error handling.

Why:
    Ensure DBLearningRepo keeps 404/403 semantics promised by the API layer.
"""
from __future__ import annotations

import os
import uuid

import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _seed_course_with_section(cur, *, teacher: str) -> dict[str, str]:
    cur.execute("select set_config('app.current_sub', %s, false)", (teacher,))
    cur.execute("insert into public.courses (title, teacher_id) values (%s, %s) returning id", (f"Repo course {uuid.uuid4()}", teacher))
    course_id = cur.fetchone()[0]
    cur.execute("insert into public.units (title, author_id) values (%s, %s) returning id", (f"Repo unit {uuid.uuid4()}", teacher))
    unit_id = cur.fetchone()[0]
    cur.execute("insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id", (unit_id, "Section", 1))
    section_id = cur.fetchone()[0]
    cur.execute("insert into public.course_modules (course_id, unit_id, position) values (%s, %s, %s) returning id", (course_id, unit_id, 1))
    module_id = cur.fetchone()[0]
    cur.execute(
        """
        insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by)
        values (%s, %s, true, now(), %s)
        on conflict (course_module_id, section_id)
        do update set visible = excluded.visible, released_at = excluded.released_at, released_by = excluded.released_by
        """,
        (module_id, section_id, teacher),
    )
    return {
        "course_id": str(course_id),
        "unit_id": str(unit_id),
        "section_id": str(section_id),
        "module_id": str(module_id),
    }


@pytest.mark.anyio
async def test_list_units_for_student_course_raises_lookup_for_non_member():
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")

    from backend.learning.repo_db import DBLearningRepo  # type: ignore

    dsn = _dsn()
    teacher = f"teacher-repo-{uuid.uuid4()}"
    outsider = f"student-repo-{uuid.uuid4()}"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            ids = _seed_course_with_section(cur, teacher=teacher)
            conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    with pytest.raises(LookupError):
        repo.list_units_for_student_course(student_sub=outsider, course_id=ids["course_id"])


@pytest.mark.anyio
async def test_list_released_sections_raises_permission_for_non_member():
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")

    from backend.learning.repo_db import DBLearningRepo  # type: ignore

    dsn = _dsn()
    teacher = f"teacher-repo-{uuid.uuid4()}"
    outsider = f"student-repo-{uuid.uuid4()}"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            ids = _seed_course_with_section(cur, teacher=teacher)
            conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    with pytest.raises(PermissionError):
        repo.list_released_sections(
            student_sub=outsider,
            course_id=ids["course_id"],
            include_materials=False,
            include_tasks=False,
            limit=10,
            offset=0,
        )
