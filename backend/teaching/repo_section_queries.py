"""Unit section SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but unit section CRUD and ordering
    form a distinct database surface. Modular section creation also creates a
    unit-module graph node through the dedicated unit-module query helper.
"""

from __future__ import annotations

from typing import List, Optional

from backend.teaching import repo_unit_module_queries as _repo_unit_module_queries


def section_exists_for_author(*, dsn: str, psycopg_module, unit_id: str, section_id: str, author_id: str) -> bool:
    """Check whether a section belongs to the unit and is visible to the author."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select 1
                from public.unit_sections
                where unit_id = %s
                  and id = %s
                """,
                (unit_id, section_id),
            )
            return cur.fetchone() is not None

# --- Unit sections ---------------------------------------------------------

def list_sections_for_author(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> List[dict]:
    """List sections of a unit authored by the caller.

    Why:
        Web adapter needs an owner-scoped listing that respects RLS and
        ordering semantics for display and validation.

    Parameters:
        unit_id: Target learning unit UUID string.
        author_id: Caller identity (OIDC sub). Used to set RLS context.

    Behavior:
        - Returns sections for the specified unit ordered by `position, id`.
        - Returns an empty list for non-owners due to RLS filtering.

    Security:
        - Sets `app.current_sub = author_id` to activate RLS policies
          (author-only access via join to `units`).
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text,
                       unit_id::text,
                       title,
                       position,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.unit_sections
                where unit_id = %s
                order by position asc, id
                """,
                (unit_id,),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "unit_id": r[1],
            "title": r[2],
            "position": r[3],
            "created_at": r[4],
            "updated_at": r[5],
        }
        for r in rows
    ]

def create_section(
    *,
    dsn: str,
    psycopg_module,
    unique_violation_cls,
    unit_id: str,
    title: str,
    author_id: str,
) -> dict:
    """Create a new section at the next position within a unit.

    Why:
        Sections are ordered within a unit. New sections append to the end
        in a concurrency-safe way.

    Parameters:
        unit_id: Target unit UUID string (must be authored by `author_id`).
        title: Section title (1..200 chars).
        author_id: Caller identity; sets RLS context.

    Behavior:
        - Validates minimal constraints (non-empty title, max length 200).
        - Computes `position = max(position) + 1` for the unit.
        - Returns persisted row as dict.

    Concurrency:
        - Locks existing rows in `unit_sections` for the unit to prevent
          race conditions when computing the next position.

    Security:
        - RLS requires the unit to be authored by `author_id`.
    """
    title = (title or "").strip()
    if not title or len(title) > 200:
        raise ValueError("invalid_title")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            # Serialize concurrent inserts by locking the parent unit row.
            # RLS ensures only the author's units are lockable/visible.
            cur.execute("select id::text, unit_type from public.units where id = %s for update", (unit_id,))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[1] or "linear").strip().lower()
            # Lock current sections for additional safety (no-ops if none exist).
            cur.execute(
                "select id from public.unit_sections where unit_id = %s for update",
                (unit_id,),
            )
            # Compute next position within the unit
            cur.execute(
                "select coalesce(max(position), 0) + 1 from public.unit_sections where unit_id = %s",
                (unit_id,),
            )
            next_pos = int(cur.fetchone()[0])
            row = None
            try:
                cur.execute(
                    """
                    insert into public.unit_sections (unit_id, title, position)
                    values (%s, %s, %s)
                    returning id::text,
                              unit_id::text,
                              title,
                              position,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (unit_id, title, next_pos),
                )
                row = cur.fetchone()
            except Exception as exc:  # rare race: recompute once on unique violation
                sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                if unique_violation_cls and isinstance(exc, unique_violation_cls) or sqlstate == "23505":
                    conn.rollback()
                    with conn.cursor() as cur2:
                        cur2.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                        cur2.execute(
                            "select coalesce(max(position), 0) + 1 from public.unit_sections where unit_id = %s",
                            (unit_id,),
                        )
                        next_pos = int(cur2.fetchone()[0])
                        cur2.execute(
                            """
                            insert into public.unit_sections (unit_id, title, position)
                            values (%s, %s, %s)
                            returning id::text,
                                      unit_id::text,
                                      title,
                                      position,
                                      to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                      to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                            """,
                            (unit_id, title, next_pos),
                        )
                        row = cur2.fetchone()
                else:
                    raise
            if row is None:
                raise RuntimeError("unit_sections insert returned no row")

            # Option B: modular units create a 1:1 module record with its own UUID.
            if unit_type == "modular":
                _repo_unit_module_queries.create_module_record_for_new_section(
                    cur=cur,
                    unit_id=unit_id,
                    section_id=row[0],
                )
            conn.commit()
    return {
        "id": row[0],
        "unit_id": row[1],
        "title": row[2],
        "position": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }

def update_section_title(*, dsn: str, psycopg_module, unit_id: str, section_id: str, title: str, author_id: str) -> Optional[dict]:
    """Update the title of a section within a unit owned by the caller.

    Why:
        Allow authors to rename sections without changing ordering.

    Behavior:
        - Returns updated row on success; None when row not visible (not found or not owned).

    Security:
        - RLS ensures only the author's sections are mutable.
    """
    if title is None:
        raise ValueError("invalid_title")
    t = (title or "").strip()
    if not t or len(t) > 200:
        raise ValueError("invalid_title")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                update public.unit_sections
                set title = %s
                where id = %s and unit_id = %s
                returning id::text,
                          unit_id::text,
                          title,
                          position,
                          to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                          to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                """,
                (t, section_id, unit_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            conn.commit()
    return {
        "id": row[0],
        "unit_id": row[1],
        "title": row[2],
        "position": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }

def delete_section(*, dsn: str, psycopg_module, unit_id: str, section_id: str, author_id: str) -> bool:
    """Delete a section and resequence remaining positions within the unit.

    Why:
        Maintain contiguous ordering (1..n) after deletions to keep UX simple.

    Behavior:
        - Returns True on delete; False if the row is not visible (not found/not owned).

    Security:
        - RLS restricts visibility to the author; non-owners get False.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            # Lock target row to ensure stable resequencing
            cur.execute(
                "select id from public.unit_sections where id = %s and unit_id = %s for update",
                (section_id, unit_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute(
                "delete from public.unit_sections where id = %s and unit_id = %s",
                (section_id, unit_id),
            )
            # Resequence positions contiguously (1..n)
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position asc, id) as rn
                  from public.unit_sections
                  where unit_id = %s
                )
                update public.unit_sections u
                set position = o.rn
                from ordered o
                where u.id = o.id
                """,
                (unit_id,),
            )
            conn.commit()
            return True

def reorder_unit_sections_owned(*, dsn: str, psycopg_module, unit_id: str, author_id: str, section_ids: List[str]) -> List[dict]:
    """Atomically reorder sections for a unit the author owns.

    Why:
        Reordering must be safe under concurrency and preserve uniqueness of
        `(unit_id, position)` without gaps or duplicates.

    Behavior:
        - Validates exact set equality of submitted vs existing IDs.
        - Updates positions to 1..n in a single transaction and returns the
          new ordered list.

    Security:
        - RLS restricts the visible `existing` set to the author's unit.
        - Cross-unit IDs are detected: existing_set check + presence in table
          → LookupError to map to 404 at the web layer.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text
                from public.unit_sections
                where unit_id = %s
                order by position asc, id
                """,
                (unit_id,),
            )
            existing = [row[0] for row in (cur.fetchall() or [])]
            if not existing:
                # Align with API contract: treat as mismatch when no sections are present
                raise ValueError("section_mismatch")
            existing_set = set(existing)
            submitted_set = set(section_ids)
            if submitted_set != existing_set or len(section_ids) != len(existing):
                extra = submitted_set - existing_set
                if extra:
                    cur.execute(
                        "select count(*) from public.unit_sections where id = any(%s)",
                        (list(extra),),
                    )
                    c = cur.fetchone()
                    if c and int(c[0]) > 0:
                        raise LookupError("section_not_in_unit")
                raise ValueError("section_mismatch")
            # Deferrable unique constraint allows in-place position updates
            cur.execute("set constraints unit_sections_unit_id_position_key deferred")
            orderings = list(range(1, len(section_ids) + 1))
            cur.execute(
                """
                with new_order as (
                  select sid, ord from unnest(%s::uuid[], %s::int[]) as t(sid, ord)
                )
                update public.unit_sections s
                set position = n.ord
                from new_order n
                where s.id = n.sid
                  and s.unit_id = %s
                """,
                (section_ids, orderings, unit_id),
            )
            cur.execute(
                """
                select id::text,
                       unit_id::text,
                       title,
                       position,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.unit_sections
                where unit_id = %s
                order by position asc, id
                """,
                (unit_id,),
            )
            rows = cur.fetchall() or []
            conn.commit()
    return [
        {
            "id": r[0],
            "unit_id": r[1],
            "title": r[2],
            "position": r[3],
            "created_at": r[4],
            "updated_at": r[5],
        }
        for r in rows
    ]

# --- Section materials -----------------------------------------------------
# --- Section materials -----------------------------------------------------
