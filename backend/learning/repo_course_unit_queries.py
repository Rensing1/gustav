"""Course and unit read queries for the Learning repository.

Why:
    DBLearningRepo is the public facade for learning persistence. Student
    course and course-unit reads are a distinct query surface, so they live in
    this small module and receive the DSN plus psycopg module from the facade.
"""

from __future__ import annotations

from typing import List
from uuid import UUID


def list_courses_for_student(*, dsn: str, psycopg_module, student_sub: str, limit: int, offset: int) -> List[dict]:
    """Return the student's courses with minimal fields, alphabetically."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select c.id::text, c.title, c.subject, c.grade_level, c.term
                  from public.courses c
                  join public.course_memberships m on m.course_id = c.id
                 where m.student_id = %s and m.ended_at is null and c.status = 'active'
                 order by c.title asc, c.id asc
                 offset %s
                 limit %s
                """,
                (student_sub, int(max(0, offset)), int(max(1, limit))),
            )
            rows = cur.fetchall()
    items: List[dict] = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "title": row[1],
                "subject": row[2],
                "grade_level": row[3],
                "term": row[4],
            }
        )
    return items


def list_units_for_student_course(*, dsn: str, psycopg_module, student_sub: str, course_id: str) -> List[dict]:
    """Return units for the student's course ordered by module position."""

    course_uuid = str(UUID(course_id))
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            # Keep the explicit membership check for API 404 semantics.
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise LookupError("not_member_or_missing")
            cur.execute(
                """
                select unit_id::text, title, summary, unit_type, module_position
                  from public.get_course_units_for_student(%s, %s)
                """,
                (student_sub, course_uuid),
            )
            rows = cur.fetchall()
    result: List[dict] = []
    for row in rows:
        result.append(
            {
                "unit": {
                    "id": row[0],
                    "title": row[1],
                    "summary": row[2],
                    "unit_type": row[3],
                },
                "position": int(row[4]) if row[4] is not None else 1,
            }
        )
    return result
