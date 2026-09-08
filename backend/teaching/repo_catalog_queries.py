"""Batched owner-scoped catalog metadata; no pagination or projection policy."""


def list_catalog_course_refs(*, dsn, psycopg_module, owner_sub: str, course_ids: list[str]) -> list[dict]:
    """Read assignments for already selected courses in one database operation.

    The authenticated owner is enforced explicitly and via transaction-local RLS.
    Input order is preserved so catalog course links retain their former order.
    Empty selections need no connection; callers retain their existing limit.
    """
    if not course_ids:
        return []
    with psycopg_module.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
        cur.execute(
            """
            select m.course_id::text, u.id::text
              from public.course_modules m
              join public.courses c on c.id = m.course_id
              join public.units u on u.id = m.unit_id
             where c.teacher_id = %s and m.course_id = any(%s::uuid[])
             order by array_position(%s::uuid[], m.course_id), m.position, m.id
            """,
            (owner_sub, course_ids, course_ids),
        )
        return [{"course_id": row[0], "unit_id": row[1]} for row in cur.fetchall()]


def list_catalog_section_summaries(*, dsn, psycopg_module, owner_sub: str, unit_ids: list[str]) -> dict[str, dict]:
    """Aggregate only the selected author's sections without fetching their bodies.

    Returns count and most recent activity per nonempty unit. Missing or foreign
    units produce no entry. Timestamp formatting matches the existing section API.
    """
    if not unit_ids:
        return {}
    with psycopg_module.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
        cur.execute(
            """
            select s.unit_id::text, count(*),
                   to_char(max(s.updated_at) at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
              from public.unit_sections s
              join public.units u on u.id = s.unit_id
             where u.author_id = %s and s.unit_id = any(%s::uuid[])
             group by s.unit_id
            """,
            (owner_sub, unit_ids),
        )
        return {row[0]: {"count": int(row[1]), "updated_at": row[2]} for row in cur.fetchall()}
