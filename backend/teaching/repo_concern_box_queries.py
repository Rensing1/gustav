"""Concern-box SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but concern-box student messages
    and teacher archive actions form a distinct database surface.
"""

from __future__ import annotations

from typing import Any


def create_concern_box_entry(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    student_sub: str,
    message_text: str,
    anonymous: bool,
) -> dict[str, Any] | None:
    text = (message_text or "").strip()
    if not text:
        raise ValueError("invalid_message_text")
    try:
        with psycopg_module.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                cur.execute(
                    """
                    select id::text,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                      from public.create_concern_box_entry(%s, %s::uuid, %s, %s)
                    """,
                    (student_sub, course_id, text, bool(anonymous)),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception:
        return None
    if row is None:
        return None
    return {"id": row[0], "created_at": row[1]}

def list_concern_box_entries_for_teacher(*, dsn: str, psycopg_module, owner_sub: str, scope: str) -> list[dict[str, Any]]:
    archived = scope == "archived"
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select e.id::text,
                       e.course_id::text,
                       c.title,
                       e.student_sub,
                       e.message_text,
                       e.anonymous,
                       to_char(e.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       case
                         when e.archived_at is null then null
                         else to_char(e.archived_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                       end
                  from public.concern_box_entries e
                  join public.courses c on c.id = e.course_id
                 where (e.archived_at is null) = %s
                 order by e.created_at desc, e.id desc
                """,
                (not archived,),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": row[0],
            "course_id": row[1],
            "course_title": row[2],
            "student_sub": row[3],
            "message_text": row[4],
            "anonymous": bool(row[5]),
            "created_at": row[6],
            "archived_at": row[7],
        }
        for row in rows
    ]

def archive_concern_box_entry_owned(*, dsn: str, psycopg_module, entry_id: str, owner_sub: str) -> bool:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                update public.concern_box_entries
                   set archived_at = now(),
                       archived_by = %s
                 where id = %s::uuid
                """,
                (owner_sub, entry_id),
            )
            updated = (cur.rowcount or 0) == 1
            conn.commit()
    return updated

def restore_concern_box_entry_owned(*, dsn: str, psycopg_module, entry_id: str, owner_sub: str) -> bool:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                update public.concern_box_entries
                   set archived_at = null,
                       archived_by = null
                 where id = %s::uuid
                """,
                (entry_id,),
            )
            updated = (cur.rowcount or 0) == 1
            conn.commit()
    return updated
