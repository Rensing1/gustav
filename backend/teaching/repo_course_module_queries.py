"""Course module SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but course module ordering,
    attached-unit read models, and module-section release state form a distinct
    database surface. The functions here receive the DSN and psycopg module from
    the facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID


def _iso(ts) -> str:
    """Return an ISO-like string for database timestamps without changing semantics."""
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    try:
        return ts.isoformat()
    except Exception:
        return str(ts)


def list_course_modules_for_owner(*, dsn: str, psycopg_module, course_id: str, owner_sub: str) -> List[dict]:
    """Return modules for a course owned by `owner_sub`, ordered by position."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select id::text,
                       course_id::text,
                       unit_id::text,
                       position,
                       context_notes,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.course_modules
                where course_id = %s
                order by position asc, id
                """,
                (course_id,),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "course_id": r[1],
            "unit_id": r[2],
            "position": r[3],
            "context_notes": r[4],
            "created_at": r[5],
            "updated_at": r[6],
        }
        for r in rows
    ]

def list_course_units_for_owner(*, dsn: str, psycopg_module, course_id: str, owner_sub: str) -> List[dict]:
    """Return attached units for a course owned by `owner_sub`.

    Why:
        The teacher student-overview needs a course-scoped unit list that is
        independent from author-only repository methods. Ordering follows the
        course-module order seen by teachers in the UI.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select u.id::text,
                       u.title,
                       m.position
                  from public.course_modules m
                  join public.courses c
                    on c.id = m.course_id
                  join public.units u
                    on u.id = m.unit_id
                 where m.course_id = %s
                   and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                 order by m.position asc, m.id
                """,
                (course_id,),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "title": r[1],
            "position": int(r[2]) if r[2] is not None else 0,
        }
        for r in rows
    ]

def create_course_module_owned(
    *,
    dsn: str,
    psycopg_module,
    unique_violation_cls,
    course_id: str,
    owner_sub: str,
    unit_id: str,
    context_notes: Optional[str],
) -> dict:
    """
    Attach a unit as a module within an owned course.

    Validation:
        - Notes trimmed to None when blank; length limited to 2000 characters.
        - Unique constraint violations bubble up as ValueError("duplicate_module").
    """
    try:
        unit_uuid = str(UUID(str(unit_id)))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid_unit_id") from exc
    notes = None
    if context_notes is not None:
        notes = context_notes.strip()
        if notes == "":
            notes = None
        if notes and len(notes) > 2000:
            raise ValueError("invalid_context_notes")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            try:
                cur.execute(
                    """
                    with next_pos as (
                      select coalesce(max(position), 0) + 1 as pos
                      from public.course_modules
                      where course_id = %s
                    )
                    insert into public.course_modules (course_id, unit_id, position, context_notes)
                    select %s, %s, next_pos.pos, %s
                    from next_pos
                    returning id::text,
                              course_id::text,
                              unit_id::text,
                              position,
                              context_notes,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (course_id, course_id, unit_uuid, notes),
                )
            except Exception as exc:
                sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                if unique_violation_cls and isinstance(exc, unique_violation_cls):
                    conn.rollback()
                    raise ValueError("duplicate_module") from exc
                if sqlstate == "23505":
                    conn.rollback()
                    raise ValueError("duplicate_module") from exc
                raise
            row = cur.fetchone()
            if not row:
                conn.rollback()
                raise PermissionError("module_insert_forbidden")
            conn.commit()
    return {
        "id": row[0],
        "course_id": row[1],
        "unit_id": row[2],
        "position": row[3],
        "context_notes": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }

def reorder_course_modules_owned(*, dsn: str, psycopg_module, course_id: str, owner_sub: str, module_ids: List[str]) -> List[dict]:
    """Reorder modules for a course owned by `owner_sub`.

    Why:
        Persist the new order without relying on deferrable constraints so
        deployments that missed the deferrable migration still behave
        correctly.

    Behavior:
        - Validates the requested set matches the course modules exactly.
        - Two-phase update inside a single transaction to preserve uniqueness:
          (1) Temporarily bump all positions in the course by N to avoid collisions.
          (2) Assign final contiguous positions 1..N in the requested order.

    Permissions:
        RLS enforced via `set_config('app.current_sub', owner_sub, true)`.
        Caller must be the course owner; otherwise, RLS hides rows and
        validation fails appropriately.
    """
    if not module_ids:
        raise ValueError("empty_reorder")
    try:
        normalized_ids = [str(UUID(str(mid))) for mid in module_ids]
    except (ValueError, TypeError) as exc:
        # Contract uses plural form
        raise ValueError("invalid_module_ids") from exc
    module_ids = normalized_ids
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select id::text
                from public.course_modules
                where course_id = %s
                order by position asc, id
                """,
                (course_id,),
            )
            existing = [row[0] for row in (cur.fetchall() or [])]
            if not existing:
                raise ValueError("no_modules")
            existing_set = set(existing)
            submitted_set = set(module_ids)
            # Distinguish between missing/extra IDs before mutating the DB.
            if submitted_set != existing_set or len(module_ids) != len(existing):
                extra = submitted_set - existing_set
                if extra:
                    cur.execute(
                        """
                        select count(*) from public.course_modules
                        where id = any(%s)
                        """,
                        (list(extra),),
                    )
                    row = cur.fetchone()
                    count = row[0] if row else 0
                    if count:
                        raise LookupError("module_not_found")
                raise ValueError("module_mismatch")
            # Phase 1: bump all positions in the target course by N to avoid
            # temporary uniqueness collisions on (course_id, position).
            bump = len(module_ids)
            cur.execute(
                "update public.course_modules set position = position + %s where course_id = %s",
                (bump, course_id),
            )
            # Phase 2: assign final positions 1..N in requested order.
            orderings = list(range(1, len(module_ids) + 1))
            cur.execute(
                """
                with new_order as (
                  select module_id, ord
                  from unnest(%s::uuid[], %s::int[]) as t(module_id, ord)
                )
                update public.course_modules m
                set position = new_order.ord
                from new_order
                where m.id = new_order.module_id
                  and m.course_id = %s
                """,
                (module_ids, orderings, course_id),
            )
            cur.execute(
                """
                select id::text,
                       course_id::text,
                       unit_id::text,
                       position,
                       context_notes,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.course_modules
                where course_id = %s
                order by position asc, id
                """,
                (course_id,),
            )
            rows = cur.fetchall() or []
            conn.commit()
    return [
        {
            "id": r[0],
            "course_id": r[1],
            "unit_id": r[2],
            "position": r[3],
            "context_notes": r[4],
            "created_at": r[5],
            "updated_at": r[6],
        }
        for r in rows
    ]

def delete_course_module_owned(*, dsn: str, psycopg_module, course_id: str, module_id: str, owner_sub: str) -> bool:
    """Delete a course module owned by `owner_sub` and resequence positions.

    Why:
        Keep contiguous ordering (1..n) after deletions to simplify the UI
        and avoid gaps in positions.

    Behavior:
        - Returns True when the row is visible and deleted; False when the
          row is not visible (not found or not owned).

    Security:
        - `set_config('app.current_sub', ...)` engages RLS policies to
          restrict visibility to course owners.
    """
    try:
        _ = str(UUID(str(module_id)))
    except (ValueError, TypeError):
        # Let the web layer map invalid UUID path params; here we just ensure
        # consistent behavior when called directly.
        pass
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            # Lock the target row to maintain a stable resequencing base
            cur.execute(
                "select id from public.course_modules where id = %s and course_id = %s for update",
                (module_id, course_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute(
                "delete from public.course_modules where id = %s and course_id = %s",
                (module_id, course_id),
            )
            # Resequence remaining modules contiguously
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position asc, id) as rn
                  from public.course_modules
                  where course_id = %s
                )
                update public.course_modules m
                set position = o.rn
                from ordered o
                where m.id = o.id
                """,
                (course_id,),
            )
            conn.commit()
            return True

def set_module_section_visibility(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    module_id: str,
    section_id: str,
    owner_sub: str,
    visible: bool,
) -> dict:
    """Set the release state for a section inside a course module.

    Parameters:
        course_id: Identifier of the course that owns the module.
        module_id: Identifier of the course module to mutate.
        section_id: Identifier of the section whose visibility changes.
        owner_sub: Subject identifier of the teacher invoking the toggle.
        visible: Target visibility flag (`True` releases the section).

    Behavior:
        - Validates module ownership and section membership within the unit.
        - Upserts a row in `module_section_releases`, recording `released_by`.

    Permissions:
        Caller must own the course; enforced via `set_config('app.current_sub', ...)`
        and the RLS policies on `course_modules`, `unit_sections`, and
        `module_section_releases`.

    Raises:
        LookupError: When the module or section does not exist for this course.
        PermissionError: When RLS denies access (non-owner).
    """
    released_at = datetime.now(timezone.utc) if visible else None
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select unit_id::text
                from public.course_modules
                where id = %s
                  and course_id = %s
                """,
                (module_id, course_id),
            )
            module_row = cur.fetchone()
            if not module_row:
                raise LookupError("module_not_found")
            unit_id = module_row[0]
            # Restrict to sections that belong to the module's unit to avoid cross-unit leakage.
            cur.execute(
                """
                select id::text
                from public.unit_sections
                where id = %s
                  and unit_id = %s
                """,
                (section_id, unit_id),
            )
            section_row = cur.fetchone()
            if not section_row:
                raise LookupError("section_not_in_module")
            try:
                cur.execute(
                    """
                    insert into public.module_section_releases (
                        course_module_id,
                        section_id,
                        visible,
                        released_at,
                        released_by
                    )
                    values (%s, %s, %s, %s, %s)
                    on conflict (course_module_id, section_id)
                    do update set
                        visible = excluded.visible,
                        released_at = excluded.released_at,
                        released_by = excluded.released_by
                    returning
                        course_module_id::text,
                        section_id::text,
                        visible,
                        to_char(released_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                        released_by
                    """,
                    (module_id, section_id, visible, released_at, owner_sub),
                )
            except Exception as exc:
                # Map typical RLS denials (e.g., policy violations) to PermissionError
                # to ensure the web layer returns 403 rather than 500.
                if getattr(exc, "sqlstate", None) in {"42501"}:  # insufficient_privilege
                    raise PermissionError("rls_denied")
                # Fallback: re-raise for upstream handling
                raise
            result = cur.fetchone()
            conn.commit()
    if not result:
        raise LookupError("visibility_update_failed")
    return {
        "course_module_id": result[0],
        "section_id": result[1],
        "visible": bool(result[2]),
        "released_at": _iso(result[3]) if result[3] is not None else None,
        "released_by": result[4],
    }

def list_module_section_releases_owned(*, dsn: str, psycopg_module, course_id: str, module_id: str, owner_sub: str) -> list[dict]:
    """List release records for sections within a course module owned by `owner_sub`.

    Security:
        - Sets `app.current_sub` to the owner for RLS.
        - Verifies that the module belongs to the given course and that the
          course is owned by `owner_sub`.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            # Verify ownership by joining courses
            cur.execute(
                """
                select m.id::text
                  from public.course_modules m
                  join public.courses c on c.id = m.course_id
                 where m.id = %s
                   and m.course_id = %s
                   and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                """,
                (module_id, course_id),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError("module_not_found")

            # Fetch release rows for the module
            cur.execute(
                """
                select course_module_id::text,
                       section_id::text,
                       visible,
                       to_char(released_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       released_by
                  from public.module_section_releases
                 where course_module_id = %s
                 order by section_id asc
                """,
                (module_id,),
            )
            rows = cur.fetchall()
    result: list[dict] = []
    for r in rows:
        result.append(
            {
                "course_module_id": r[0],
                "section_id": r[1],
                "visible": bool(r[2]),
                "released_at": _iso(r[3]) if r[3] is not None else None,
                "released_by": r[4],
            }
        )
    return result

# --- Owner-scoped helpers (RLS-friendly) ------------------------------------
