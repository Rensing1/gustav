"""Course membership SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but roster reads and membership
    mutations form a distinct database surface. The service-role delete fallback
    is passed in explicitly so this module does not reach back into the facade.
"""

from __future__ import annotations

from typing import List, Tuple


def list_courses_for_student(*, dsn: str, psycopg_module, student_id: str, limit: int, offset: int) -> List[dict]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_id,))
            cur.execute(
                """
                select c.id::text, c.title, c.subject, c.grade_level, c.term, c.teacher_id,
                       to_char(c.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(c.updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.courses c
                join public.course_memberships m on m.course_id = c.id
                where m.student_id = %s and m.ended_at is null and c.status = 'active'
                order by c.created_at desc, c.id
                limit %s offset %s
                """,
                (student_id, int(limit), int(offset)),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "title": r[1],
            "subject": r[2],
            "grade_level": r[3],
            "term": r[4],
            "teacher_id": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]


def list_active_courses_for_owner_member(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    student_sub: str,
    limit: int,
    offset: int,
) -> List[dict]:
    """Page active courses where the caller is owner and the learner is enrolled.

    Why:
        Learner diagnostics paginate the intersection of course ownership and
        active membership. Doing that intersection in one query avoids scanning
        every teacher course and issuing a membership query for each result.

    Permissions:
        `owner_sub` must own every returned course. RLS remains active and the
        explicit predicates keep this repository boundary fail-closed.
    """

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select c.id::text, c.title
                  from public.courses c
                 where c.teacher_id = %s
                   and c.status = 'active'
                   and exists (
                       select 1
                         from public.course_memberships m
                        where m.course_id = c.id
                          and m.student_id = %s
                          and m.ended_at is null
                   )
                 order by c.created_at desc, c.id
                 limit %s offset %s
                """,
                (owner_sub, student_sub, int(limit), int(offset)),
            )
            rows = cur.fetchall() or []
    return [{"id": row[0], "title": row[1]} for row in rows]


def course_has_member(*, dsn: str, psycopg_module, course_id: str, owner_sub: str, student_sub: str) -> bool:
    """Check membership using the existing owner-scoped roster helper."""
    page_size = 50
    offset = 0
    while True:
        page = list_members_for_owner(dsn=dsn, psycopg_module=psycopg_module, course_id=course_id, owner_sub=owner_sub, limit=page_size, offset=offset)
        if not page:
            return False
        if any(str(member_sub) == str(student_sub) for member_sub, _joined_at in page):
            return True
        if len(page) < page_size:
            return False
        offset += page_size

def list_members_for_owner(*, dsn: str, psycopg_module, course_id: str, owner_sub: str, limit: int, offset: int) -> List[Tuple[str, str]]:
    """Return the roster for a course owned by `owner_sub` using the SECURITY DEFINER helper.

    Why:
        We rely on `public.get_course_members` so that the owner can read members without
        triggering RLS recursion on `course_memberships`.

    Behavior:
        - Returns `(student_id, joined_at_iso)` tuples ordered by join time.
        - Enforces pagination via helper-level clamping (max 50).

    Permissions:
        Caller must be a teacher who owns the course; helper enforces ownership.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            # Helper runs with definer privileges and applies its own limit/offset guards.
            cur.execute(
                """
                select student_id,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.get_course_members(%s, %s, %s, %s)
                """,
                (owner_sub, course_id, int(limit), int(offset)),
            )
            rows = cur.fetchall() or []
    return [(r[0], r[1]) for r in rows]

def add_member_owned(*, dsn: str, psycopg_module, course_id: str, owner_sub: str, student_id: str) -> bool:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                insert into public.course_memberships (course_id, student_id)
                select %s, %s
                 where public.course_exists_for_owner(%s, %s)
                on conflict (course_id, student_id) do update
                  set ended_at = null, ended_by = null, created_at = now()
                where course_memberships.ended_at is not null
                """,
                (course_id, student_id, owner_sub, course_id),
            )
            inserted = cur.rowcount == 1
            conn.commit()
    return inserted

def remove_member_owned(
    *,
    dsn: str,
    psycopg_module,
    service_dsn: str | None,
    service_fallback_allowed,
    logger,
    course_id: str,
    owner_sub: str,
    student_id: str,
) -> None:
    """End a membership without deleting the learner's history.

    Why:
        Teachers must be able to unenroll students from their own courses.
        Under RLS, deletion is allowed only when `app.current_sub` matches
        the course owner. Some environments may still block the delete
        (e.g., drifted policies). To keep UX reliable while preserving
        security, we try under the limited role first. If RLS blocks the
        row (policy drift), we invoke a SECURITY DEFINER helper that
        verifies ownership and performs the delete without relying on RLS.
        As a last resort in dev/test, we fall back to a service-role DSN
        only when configured and only after ownership was verified by the
        route.

    Parameters:
        course_id: Target course UUID (text accepted by psycopg parameter).
        owner_sub: Subject identifier of the teacher (OIDC `sub`).
        student_id: Subject identifier of the student to remove.

    Security:
        - First attempt uses the limited-role DSN (RLS enforced).
        - Secondary fallback uses SECURITY DEFINER helper
          `public.remove_course_membership(owner, course, student)`.
        - Optional final fallback uses `SERVICE_ROLE_DSN` (or test variant) to
          execute the delete when RLS prevents it, but the route has
          already verified ownership via a SECURITY DEFINER helper.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                update public.course_memberships
                   set ended_at = now(), ended_by = %s
                 where course_id = %s and student_id = %s and ended_at is null
                   and public.course_exists_for_owner(%s, course_id)
                """,
                (owner_sub, course_id, student_id, owner_sub),
            )
            conn.commit()

def student_has_course(*, dsn: str, psycopg_module, course_id: str, student_sub: str) -> bool:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select exists (
                  select 1
                    from public.course_memberships
                   where course_id = %s
                     and student_id = %s
                )
                """,
                (course_id, student_sub),
            )
            row = cur.fetchone()
    return bool((row or [False])[0])

def add_member(*, dsn: str, psycopg_module, course_id: str, student_id: str) -> bool:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.course_memberships (course_id, student_id)
                values (%s, %s)
                on conflict (course_id, student_id) do update
                  set ended_at = null, ended_by = null, created_at = now()
                """,
                (course_id, student_id),
            )
            inserted = cur.rowcount == 1
            conn.commit()
    return inserted

def list_members(*, dsn: str, psycopg_module, course_id: str, limit: int, offset: int) -> List[Tuple[str, str]]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select student_id,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.course_memberships
                where course_id = %s
                order by created_at asc, student_id
                limit %s offset %s
                """,
                (course_id, int(limit), int(offset)),
            )
            rows = cur.fetchall() or []
    return [(r[0], r[1]) for r in rows]

def remove_member(*, dsn: str, psycopg_module, course_id: str, student_id: str) -> None:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update public.course_memberships set ended_at = now() where course_id = %s and student_id = %s and ended_at is null",
                (course_id, student_id),
            )
            conn.commit()
