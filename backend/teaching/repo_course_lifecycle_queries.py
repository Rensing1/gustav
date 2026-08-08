"""Course lifecycle persistence queries.

Why:
    Archiving, former memberships, personal portfolios and destructive jobs
    share one lifecycle boundary. Keeping their SQL here prevents the HTTP
    adapters from knowing PostgreSQL details and keeps owner checks atomic.
"""

from __future__ import annotations

from typing import Any


def _course(row) -> dict[str, Any]:
    subject, grade_level, school_year_start = row[2], row[3], row[5]
    return {
        "id": row[0],
        "title": row[1],
        "subject": subject,
        "grade_level": grade_level,
        "term": row[4],
        "school_year_start": school_year_start,
        "status": row[6],
        "archived_at": row[7],
        "archived_by": row[8],
        "metadata_complete": bool(
            str(subject or "").strip()
            and str(grade_level or "").strip()
            and school_year_start is not None
        ),
        "teacher_id": row[9],
        "created_at": row[10],
        "updated_at": row[11],
    }


def list_teacher_courses(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    status: str,
    query: str,
    school_year_start: int | None,
    subject: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Return the filtered owner catalog without per-course count queries."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select c.id::text, c.title, c.subject, c.grade_level, c.term,
                       c.school_year_start, c.status,
                       to_char(c.archived_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       c.archived_by, c.teacher_id,
                       to_char(c.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(c.updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       count(distinct m.student_id) filter (where c.status = 'archived' or m.ended_at is null),
                       count(distinct cm.id)
                  from public.courses c
                  left join public.course_memberships m on m.course_id = c.id
                  left join public.course_modules cm on cm.course_id = c.id
                 where c.teacher_id = %s
                   and c.status = %s
                   and (%s = '' or c.title ilike '%%' || %s || '%%' or coalesce(c.subject, '') ilike '%%' || %s || '%%')
                   and (%s::integer is null or c.school_year_start = %s::integer)
                   and (%s = '' or c.subject = %s)
                 group by c.id
                 order by
                   case when %s = 'archived' then c.school_year_start end desc nulls last,
                   c.title asc, c.id asc
                 offset %s limit %s
                """,
                (
                    owner_sub,
                    status,
                    query,
                    query,
                    query,
                    school_year_start,
                    school_year_start,
                    subject,
                    subject,
                    status,
                    max(0, int(offset)),
                    max(1, min(100, int(limit))),
                ),
            )
            rows = cur.fetchall() or []
    result = []
    for row in rows:
        item = _course(row[:12])
        item["members_count"] = int(row[12] or 0)
        item["units_count"] = int(row[13] or 0)
        result.append(item)
    return result


def archive_course(*, dsn: str, psycopg_module, course_id: str, owner_sub: str) -> dict[str, Any]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select (r).id::text, (r).title, (r).subject, (r).grade_level, (r).term,
                       (r).school_year_start, (r).status,
                       to_char((r).archived_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       (r).archived_by, (r).teacher_id,
                       to_char((r).created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char((r).updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                  from (select public.archive_course_owned(%s, %s) r) q
                """,
                (course_id, owner_sub),
            )
            row = cur.fetchone()
            conn.commit()
    return _course(row)


def archive_courses(*, dsn: str, psycopg_module, course_ids: list[str], owner_sub: str) -> list[dict[str, Any]]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """select id::text, title, subject, grade_level, term, school_year_start, status,
                          to_char(archived_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"+00:00\"'),
                          archived_by, teacher_id,
                          to_char(created_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"+00:00\"'),
                          to_char(updated_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"+00:00\"')
                     from public.archive_courses_owned(%s::uuid[], %s)""",
                (course_ids, owner_sub),
            )
            rows = cur.fetchall() or []
            conn.commit()
    return [_course(row) for row in rows]


def restore_course(*, dsn: str, psycopg_module, course_id: str, owner_sub: str) -> dict[str, Any]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select (r).id::text, (r).title, (r).subject, (r).grade_level, (r).term,
                       (r).school_year_start, (r).status,
                       to_char((r).archived_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       (r).archived_by, (r).teacher_id,
                       to_char((r).created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char((r).updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                  from (select public.restore_course_owned(%s, %s) r) q
                """,
                (course_id, owner_sub),
            )
            row = cur.fetchone()
            conn.commit()
    return _course(row)


def end_membership(*, dsn: str, psycopg_module, course_id: str, owner_sub: str, student_sub: str) -> bool:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                update public.course_memberships m
                   set ended_at = now(), ended_by = %s
                 where m.course_id = %s and m.student_id = %s and m.ended_at is null
                   and public.course_exists_for_owner(%s, m.course_id)
                """,
                (owner_sub, course_id, student_sub, owner_sub),
            )
            changed = bool(cur.rowcount)
            conn.commit()
    return changed


def list_personal_courses(*, dsn: str, psycopg_module, student_sub: str, scope: str, limit: int, offset: int) -> list[dict]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                "select id::text, title, subject, grade_level, term, school_year_start, status, membership_status from public.list_personal_courses(%s, %s, %s, %s)",
                (student_sub, scope, limit, offset),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": row[0], "title": row[1], "subject": row[2], "grade_level": row[3],
            "term": row[4], "school_year_start": row[5], "status": row[6], "membership_status": row[7],
        }
        for row in rows
    ]


def personal_portfolio(*, dsn: str, psycopg_module, course_id: str, student_sub: str) -> list[dict]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute("select * from public.personal_course_portfolio(%s, %s)", (course_id, student_sub))
            rows = cur.fetchall() or []
    return [
        {
            "id": str(row[0]), "kind": row[1], "intent": row[2],
            "created_at": row[3].isoformat(), "completed_at": row[4].isoformat() if row[4] else None,
            "text_body": row[5], "feedback_md": row[6], "analysis_json": row[7],
            "storage_key": row[8], "mime_type": row[9],
            "dialog_session_id": str(row[10]) if row[10] else None, "task_snapshot": row[11],
        }
        for row in rows
    ]


def create_export_job(*, dsn: str, psycopg_module, course_id: str, student_sub: str) -> dict:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select (j).id::text, (j).course_id::text, (j).status, (j).requested_at,
                       (j).expires_at, (j).storage_key, (j).error_code
                  from (select public.create_learning_export_job_owned(%s, %s) j) q
                """,
                (course_id, student_sub),
            )
            row = cur.fetchone()
            conn.commit()
    return _export_job(row)


def get_export_job(*, dsn: str, psycopg_module, export_id: str, student_sub: str) -> dict | None:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                "select id::text, course_id::text, status, requested_at, expires_at, storage_key, error_code from public.learning_export_jobs where id = %s and student_sub = %s",
                (export_id, student_sub),
            )
            row = cur.fetchone()
    return _export_job(row) if row else None


def _export_job(row) -> dict:
    status = "expired" if row[4] and row[4].timestamp() <= __import__("time").time() else row[2]
    return {
        "id": row[0], "course_id": row[1], "status": status,
        "requested_at": row[3].isoformat(), "expires_at": row[4].isoformat(),
        "storage_key": row[5], "error_code": row[6],
    }


def _deletion_job(row) -> dict:
    """Map the stable owner-visible deletion-job projection."""

    return {
        "id": row[0],
        "course_id": row[1],
        "course_title": row[2],
        "status": row[3],
        "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
        "started_at": row[5].isoformat() if row[5] and hasattr(row[5], "isoformat") else row[5],
        "completed_at": row[6].isoformat() if row[6] and hasattr(row[6], "isoformat") else row[6],
        "error_code": row[7],
    }


def list_deletion_jobs(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    include_completed: bool,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """List deletion jobs through RLS and an explicit owner predicate."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select id::text, course_id::text, course_title, status, created_at,
                       started_at, completed_at, error_code
                  from public.course_deletion_jobs
                 where owner_sub = %s
                   and (%s or status <> 'completed')
                 order by created_at desc, id desc
                 offset %s limit %s
                """,
                (owner_sub, include_completed, max(0, offset), max(1, min(100, limit))),
            )
            rows = cur.fetchall() or []
    return [_deletion_job(row) for row in rows]


def get_deletion_job(
    *, dsn: str, psycopg_module, job_id: str, owner_sub: str
) -> dict[str, Any] | None:
    """Read one deletion job without revealing jobs owned by another teacher."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select id::text, course_id::text, course_title, status, created_at,
                       started_at, completed_at, error_code
                  from public.course_deletion_jobs
                 where id = %s and owner_sub = %s
                """,
                (job_id, owner_sub),
            )
            row = cur.fetchone()
    return _deletion_job(row) if row else None


def deletion_impact(*, dsn: str, psycopg_module, course_id: str, owner_sub: str) -> dict | None:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute("select public.course_deletion_impact_owned(%s, %s)", (course_id, owner_sub))
            row = cur.fetchone()
    return row[0] if row and row[0] else None


def queue_deletion(*, dsn: str, psycopg_module, course_id: str, owner_sub: str, confirmation_title: str, confirm_student_data_loss: bool) -> dict:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select (j).id::text, (j).course_id::text, (j).course_title,
                       (j).status, (j).created_at, (j).started_at,
                       (j).completed_at, (j).error_code
                  from (select public.queue_course_deletion_owned(%s, %s, %s, %s) j) q
                """,
                (course_id, owner_sub, confirmation_title, confirm_student_data_loss),
            )
            row = cur.fetchone()
            conn.commit()
    return _deletion_job(row)
