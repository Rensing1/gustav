"""Private learner portfolio and export-job queries."""

from __future__ import annotations


def list_courses(*, dsn: str, psycopg_module, student_sub: str, scope: str, limit: int, offset: int) -> list[dict]:
    normalized_scope = "past" if scope == "past" else "current"
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                "select id::text, title, subject, grade_level, term, school_year_start, status, membership_status from public.list_personal_courses(%s, %s, %s, %s)",
                (student_sub, normalized_scope, limit, offset),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": row[0], "title": row[1], "subject": row[2], "grade_level": row[3],
            "term": row[4], "school_year_start": row[5], "status": row[6], "membership_status": row[7],
        }
        for row in rows
    ]


def portfolio(*, dsn: str, psycopg_module, course_id: str, student_sub: str) -> list[dict]:
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


def create_export(*, dsn: str, psycopg_module, course_id: str, student_sub: str) -> dict:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select (j).id::text, (j).course_id::text, (j).status,
                       (j).requested_at, (j).expires_at, (j).storage_key, (j).error_code
                  from (select public.create_learning_export_job_owned(%s, %s) j) q
                """,
                (course_id, student_sub),
            )
            row = cur.fetchone()
            conn.commit()
    return _job(row)


def get_export(*, dsn: str, psycopg_module, export_id: str, student_sub: str) -> dict | None:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                "select id::text, course_id::text, status, requested_at, expires_at, storage_key, error_code from public.learning_export_jobs where id = %s and student_sub = %s",
                (export_id, student_sub),
            )
            row = cur.fetchone()
    return _job(row) if row else None


def latest_export(*, dsn: str, psycopg_module, course_id: str, student_sub: str) -> dict | None:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """select id::text, course_id::text, status, requested_at, expires_at, storage_key, error_code
                     from public.learning_export_jobs
                    where course_id = %s and student_sub = %s
                    order by requested_at desc, id desc limit 1""",
                (course_id, student_sub),
            )
            row = cur.fetchone()
    return _job(row) if row else None


def _job(row) -> dict:
    from datetime import datetime, timezone

    status = "expired" if row[4] <= datetime.now(timezone.utc) else row[2]
    return {
        "id": row[0], "course_id": row[1], "status": status,
        "requested_at": row[3].isoformat(), "expires_at": row[4].isoformat(),
        "storage_key": row[5], "error_code": row[6],
    }
