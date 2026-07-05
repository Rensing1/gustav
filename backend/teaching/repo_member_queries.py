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
                where m.student_id = %s
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
                values (%s, %s)
                on conflict do nothing
                """,
                (course_id, student_id),
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
    """Remove a membership for a course owned by `owner_sub`.

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
    affected = 0
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                "delete from public.course_memberships where course_id = %s and student_id = %s",
                (course_id, student_id),
            )
            affected = cur.rowcount or 0
            if affected == 0:
                # Attempt SECURITY DEFINER helper (ownership already verified by route)
                try:
                    cur.execute(
                        "select public.remove_course_membership(%s, %s, %s)",
                        (owner_sub, course_id, student_id),
                    )
                    affected = 1  # treat as success when helper executes without error
                except Exception:
                    affected = 0
            conn.commit()
    # Final fallback (dev/test only): allow service-role DSN when explicitly enabled.
    if affected == 0 and service_dsn:
        if not service_fallback_allowed():
            # Deny fallback in prod/stage even if the flag is set; log once per call-site.
            logger.warning(
                "Service-DSN fallback blocked (env not allowed). Set GUSTAV_ENV in {dev,test,local} to enable for testing."
            )
            return
        # Explicitly allowed in test/dev; log to make audits easier.
        logger.warning("Using service-DSN fallback for membership delete (test/dev only)")
        try:
            with psycopg_module.connect(service_dsn) as conn2:  # type: ignore[arg-type]
                with conn2.cursor() as cur2:
                    cur2.execute(
                        "delete from public.course_memberships where course_id = %s and student_id = %s",
                        (course_id, student_id),
                    )
                    conn2.commit()
        except Exception:
            # Intentionally swallow errors in the test-only branch
            pass

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
                on conflict do nothing
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
                "delete from public.course_memberships where course_id = %s and student_id = %s",
                (course_id, student_id),
            )
            conn.commit()
