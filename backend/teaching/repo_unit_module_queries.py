"""Unit module graph SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but modular-unit graph authoring
    has its own database surface: phases, modules, dependency edges, movement,
    and k-of-n unlock settings. The functions here receive the DSN and psycopg
    module from the facade so tests can keep monkeypatching the outer repo.
"""

from __future__ import annotations

from typing import List, Optional


_UNSET = object()


def _is_unset(value: object) -> bool:
    """Accept unset sentinels from DBTeachingRepo and this module."""
    if value is _UNSET:
        return True
    return value.__class__ is object


def create_module_record_for_new_section(*, cur, unit_id: str, section_id: str) -> None:
    """Create the module graph node that backs a newly created modular section."""

    cur.execute(
        """
        select id::text
        from public.unit_phases
        where unit_id = %s::uuid
        order by position asc, id asc
        limit 1
        for update
        """,
        (unit_id,),
    )
    phase_row = cur.fetchone()
    if not phase_row:
        # Defensive self-healing: keep modular section creation available even
        # if all phases were deleted earlier.
        cur.execute(
            """
            insert into public.unit_phases (unit_id, title, position)
            values (%s::uuid, %s, %s)
            returning id::text
            """,
            (unit_id, "Phase 1", 1),
        )
        created_phase_row = cur.fetchone()
        phase_id = (created_phase_row or [None])[0]
        if not phase_id:
            raise RuntimeError("modular_unit_missing_phase")
    else:
        phase_id = phase_row[0]
    cur.execute(
        """
        select coalesce(max(position_in_phase), 0) + 1
        from public.unit_modules
        where phase_id = %s::uuid
        """,
        (phase_id,),
    )
    next_pos_in_phase = int(cur.fetchone()[0])
    cur.execute(
        """
        insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase)
        values (%s::uuid, %s::uuid, %s::uuid, %s)
        """,
        (unit_id, section_id, phase_id, next_pos_in_phase),
    )


def list_unit_phases_for_author(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> List[dict]:
    """List phases of a modular unit authored by the caller."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")
            cur.execute(
                """
                select id::text,
                       unit_id::text,
                       title,
                       position,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                  from public.unit_phases
                 where unit_id = %s
                 order by position asc, id asc
                """,
                (unit_id,),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "unit_id": r[1],
            "title": r[2],
            "position": int(r[3] or 1),
            "created_at": r[4],
            "updated_at": r[5],
        }
        for r in rows
    ]

def create_unit_phase(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    title: str,
    author_id: str,
    after_phase_id: str | None = None,
) -> dict:
    """Create a phase after an optional anchor while holding the unit lock."""
    title = (title or "").strip()
    if not title or len(title) > 200:
        raise ValueError("invalid_title")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select unit_type from public.units where id = %s and author_id = %s for update",
                (unit_id, author_id),
            )
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")
            if after_phase_id:
                cur.execute(
                    "select position from public.unit_phases where id = %s::uuid and unit_id = %s::uuid",
                    (after_phase_id, unit_id),
                )
                anchor_row = cur.fetchone()
                if not anchor_row:
                    raise ValueError("invalid_after_phase_id")
                next_pos = int(anchor_row[0]) + 1
                # Positions are unique per unit. Deferring the constraint lets the
                # transaction shift all following phases before inserting the gap.
                cur.execute("set constraints unit_phases_unit_id_position_key deferred")
                cur.execute(
                    """
                    update public.unit_phases
                       set position = position + 1
                     where unit_id = %s::uuid
                       and position >= %s
                    """,
                    (unit_id, next_pos),
                )
            else:
                cur.execute(
                    "select coalesce(max(position), 0) + 1 from public.unit_phases where unit_id = %s::uuid",
                    (unit_id,),
                )
                next_pos = int(cur.fetchone()[0])
            cur.execute(
                """
                insert into public.unit_phases (unit_id, title, position)
                values (%s::uuid, %s, %s)
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
            conn.commit()
    return {
        "id": row[0],
        "unit_id": row[1],
        "title": row[2],
        "position": int(row[3] or 1),
        "created_at": row[4],
        "updated_at": row[5],
    }

def update_unit_phase_title(*, dsn: str, psycopg_module, unit_id: str, phase_id: str, title: str, author_id: str) -> Optional[dict]:
    """Rename a phase within a modular unit authored by the caller."""
    if title is None:
        raise ValueError("invalid_title")
    t = (title or "").strip()
    if not t or len(t) > 200:
        raise ValueError("invalid_title")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")
            cur.execute(
                """
                update public.unit_phases
                set title = %s
                where id = %s and unit_id = %s
                returning id::text,
                          unit_id::text,
                          title,
                          position,
                          to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                          to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                """,
                (t, phase_id, unit_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            conn.commit()
    return {
        "id": row[0],
        "unit_id": row[1],
        "title": row[2],
        "position": int(row[3] or 1),
        "created_at": row[4],
        "updated_at": row[5],
    }

def reorder_unit_phases_owned(*, dsn: str, psycopg_module, unit_id: str, author_id: str, phase_ids: List[str]) -> List[dict]:
    """Atomically reorder phases for a modular unit the author owns."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select id::text
                from public.unit_phases
                where unit_id = %s
                order by position asc, id
                """,
                (unit_id,),
            )
            existing = [row[0] for row in (cur.fetchall() or [])]
            if not existing:
                raise ValueError("phase_mismatch")
            existing_set = set(existing)
            submitted_set = set(phase_ids)
            if submitted_set != existing_set or len(phase_ids) != len(existing):
                extra = submitted_set - existing_set
                if extra:
                    cur.execute("select count(*) from public.unit_phases where id = any(%s)", (list(extra),))
                    c = cur.fetchone()
                    if c and int(c[0]) > 0:
                        raise LookupError("phase_not_in_unit")
                raise ValueError("phase_mismatch")

            cur.execute("set constraints unit_phases_unit_id_position_key deferred")
            orderings = list(range(1, len(phase_ids) + 1))
            cur.execute(
                """
                with new_order as (
                  select pid, ord from unnest(%s::uuid[], %s::int[]) as t(pid, ord)
                )
                update public.unit_phases p
                set position = n.ord
                from new_order n
                where p.id = n.pid
                  and p.unit_id = %s
                """,
                (phase_ids, orderings, unit_id),
            )
            cur.execute(
                """
                select id::text,
                       unit_id::text,
                       title,
                       position,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                  from public.unit_phases
                 where unit_id = %s
                 order by position asc, id asc
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
            "position": int(r[3] or 1),
            "created_at": r[4],
            "updated_at": r[5],
        }
        for r in rows
    ]

# --- Unit modules (modular units; Option B) ------------------------------

def list_unit_modules_for_author(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> List[dict]:
    """List modules (module_id) for a modular unit authored by the caller.

    Option B:
        Modules are graph nodes stored in `public.unit_modules` (module_id),
        and map 1:1 to a content container `public.unit_sections` via
        `unit_modules.section_id`.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")
            cur.execute(
                """
                select um.id::text,
                       um.unit_id::text,
                       um.section_id::text,
                       um.phase_id::text,
                       um.position_in_phase,
                       um.required_prereq_count,
                       s.title
                  from public.unit_modules um
                  join public.unit_sections s on s.id = um.section_id
                  join public.unit_phases p on p.id = um.phase_id
                 where um.unit_id = %s
                 order by p.position asc, um.position_in_phase asc, um.id asc
                """,
                (unit_id,),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "unit_id": r[1],
            "section_id": r[2],
            "phase_id": r[3],
            "position_in_phase": int(r[4] or 1),
            "required_prereq_count": int(r[5] or 0),
            "title": r[6],
        }
        for r in rows
    ]

def get_unit_module_for_author(*, dsn: str, psycopg_module, unit_id: str, module_id: str, author_id: str) -> Optional[dict]:
    """Resolve module metadata for a modular unit authored by the caller.

    Returns:
        Dict with keys: id (module_id), unit_id, section_id, phase_id, title.
        None when the module is not visible to the caller.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")
            cur.execute(
                """
                select um.id::text,
                       um.unit_id::text,
                       um.section_id::text,
                       um.phase_id::text,
                       um.position_in_phase,
                       um.required_prereq_count,
                       s.title
                  from public.unit_modules um
                  join public.unit_sections s on s.id = um.section_id
                 where um.unit_id = %s
                   and um.id = %s::uuid
                """,
                (unit_id, module_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "unit_id": row[1],
        "section_id": row[2],
        "phase_id": row[3],
        "position_in_phase": int(row[4] or 1),
        "required_prereq_count": int(row[5] or 0),
        "title": row[6],
    }

def list_unit_module_edges_for_author(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> List[dict]:
    """List dependency edges for a modular unit authored by the caller.

    Returns:
        List of dicts: { "from": <module_id>, "to": <module_id> }.

    Security:
        Activates RLS by setting `app.current_sub = author_id`.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")
            cur.execute(
                """
                select from_module_id::text, to_module_id::text
                  from public.unit_module_edges
                 where unit_id = %s::uuid
                 order by from_module_id asc, to_module_id asc
                """,
                (unit_id,),
            )
            rows = cur.fetchall() or []
    return [{"from": r[0], "to": r[1]} for r in rows]

def create_unit_module_for_author(*, dsn: str, psycopg_module, unit_id: str, phase_id: str, title: str, author_id: str) -> dict:
    """Create a module in the given phase (Option B).

    Option B:
        A module is a graph node (`public.unit_modules.id`) that maps 1:1
        to a content container (`public.unit_sections.id`) via
        `unit_modules.section_id`.

    Behavior:
        - Validates unit ownership and that the unit is modular.
        - Validates the phase belongs to the unit.
        - Creates a new `unit_sections` row (append position within unit).
        - Creates the `unit_modules` row in the given phase (append within phase).

    Returns:
        Dict with module_id + backing section_id:
        {id, unit_id, section_id, phase_id, position_in_phase, required_prereq_count, title}
    """
    t = (title or "").strip()
    if not t or len(t) > 200:
        raise ValueError("invalid_title")

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select unit_type from public.units where id = %s and author_id = %s for update",
                (unit_id, author_id),
            )
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                "select 1 from public.unit_phases where id = %s::uuid and unit_id = %s::uuid",
                (phase_id, unit_id),
            )
            if not cur.fetchone():
                raise LookupError("phase_not_found")

            # Append a backing section to keep existing content tables intact.
            cur.execute("select coalesce(max(position), 0) + 1 from public.unit_sections where unit_id = %s", (unit_id,))
            next_section_pos = int(cur.fetchone()[0])
            cur.execute(
                """
                insert into public.unit_sections (unit_id, title, position)
                values (%s::uuid, %s, %s)
                returning id::text
                """,
                (unit_id, t, next_section_pos),
            )
            section_id = (cur.fetchone() or [None])[0]
            if not section_id:
                raise RuntimeError("unit_sections insert returned no id")

            # Append module within the target phase.
            cur.execute(
                """
                select coalesce(max(position_in_phase), 0) + 1
                from public.unit_modules
                where phase_id = %s::uuid
                """,
                (phase_id,),
            )
            next_pos_in_phase = int(cur.fetchone()[0])
            cur.execute(
                """
                insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase)
                values (%s::uuid, %s::uuid, %s::uuid, %s)
                returning id::text, required_prereq_count
                """,
                (unit_id, section_id, phase_id, next_pos_in_phase),
            )
            module_row = cur.fetchone()
            if not module_row:
                raise RuntimeError("unit_modules insert returned no row")
            module_id, required_prereq_count = module_row[0], int(module_row[1] or 0)
            conn.commit()
    return {
        "id": module_id,
        "unit_id": unit_id,
        "section_id": section_id,
        "phase_id": phase_id,
        "position_in_phase": next_pos_in_phase,
        "required_prereq_count": required_prereq_count,
        "title": t,
    }

def create_unit_module_edge_for_author(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str, from_module_id: str, to_module_id: str, author_id: str
) -> dict:
    """Create a directed dependency edge `from -> to` (author only).

    Option 1 (k-of-n default):
        `unit_modules.required_prereq_count` stores the configured `k`.

        When the stored `k` equals the current number of incoming edges `n`
        (k==n), we treat the module as being in "auto" mode and keep `k`
        synced to `n` as edges are added/removed.

        This yields a sensible default (new module with 0 edges => k==0),
        while still allowing manual overrides (set k to a different value).
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            # Lock the target module row so concurrent edge edits serialize.
            cur.execute(
                """
                select required_prereq_count
                  from public.unit_modules
                 where unit_id = %s::uuid
                   and id = %s::uuid
                 for update
                """,
                (unit_id, to_module_id),
            )
            mod_row = cur.fetchone()
            current_k = int((mod_row or [0])[0] or 0)

            # Capture current incoming edge count (n) before inserting.
            cur.execute(
                """
                select count(*)
                  from public.unit_module_edges
                 where unit_id = %s::uuid
                   and to_module_id = %s::uuid
                """,
                (unit_id, to_module_id),
            )
            old_n = int((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                insert into public.unit_module_edges (unit_id, from_module_id, to_module_id)
                values (%s::uuid, %s::uuid, %s::uuid)
                returning from_module_id::text, to_module_id::text
                """,
                (unit_id, from_module_id, to_module_id),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("unit_module_edges insert returned no row")

            # Auto mode: when k==n, keep k in sync with n.
            if current_k == old_n:
                new_n = old_n + 1
                cur.execute(
                    """
                    update public.unit_modules
                       set required_prereq_count = %s
                     where unit_id = %s::uuid
                       and id = %s::uuid
                    """,
                    (new_n, unit_id, to_module_id),
                )

            conn.commit()
    return {"from": row[0], "to": row[1]}

def delete_unit_module_edge_for_author(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str, from_module_id: str, to_module_id: str, author_id: str
) -> bool:
    """Delete a directed dependency edge `from -> to` (author only)."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            # Lock the target module row so edge + k updates remain consistent.
            cur.execute(
                """
                select required_prereq_count
                  from public.unit_modules
                 where unit_id = %s::uuid
                   and id = %s::uuid
                 for update
                """,
                (unit_id, to_module_id),
            )
            mod_row = cur.fetchone()
            current_k = int((mod_row or [0])[0] or 0)

            cur.execute(
                """
                select count(*)
                  from public.unit_module_edges
                 where unit_id = %s::uuid
                   and to_module_id = %s::uuid
                """,
                (unit_id, to_module_id),
            )
            old_n = int((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                delete from public.unit_module_edges
                where unit_id = %s::uuid
                  and from_module_id = %s::uuid
                  and to_module_id = %s::uuid
                """,
                (unit_id, from_module_id, to_module_id),
            )
            deleted = int(cur.rowcount or 0)

            if deleted > 0 and current_k == old_n:
                new_n = max(old_n - 1, 0)
                cur.execute(
                    """
                    update public.unit_modules
                       set required_prereq_count = %s
                     where unit_id = %s::uuid
                       and id = %s::uuid
                    """,
                    (new_n, unit_id, to_module_id),
                )

            conn.commit()
    return deleted > 0

def reorder_unit_phase_modules_owned(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str, phase_id: str, author_id: str, module_ids: List[str]
) -> List[dict]:
    """Reorder (and move) modules within a phase (author only).

    Semantics:
        - The provided `module_ids` define the desired top-to-bottom order
          for the target phase.
        - Modules listed that currently live in another phase are moved
          into the target phase.
        - Modules already in the target phase but not mentioned are
          appended afterwards (stable order).
        - All affected phases are compacted to positions 1..n.

    Safety:
        A DB constraint trigger validates that existing edges remain valid
        after the move/reorder. Violations raise CHECK VIOLATION at commit.
    """
    if not module_ids:
        raise ValueError("empty_module_ids")
    if len(module_ids) != len(set(module_ids)):
        raise ValueError("duplicate_module_ids")

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute("select 1 from public.unit_phases where id = %s::uuid and unit_id = %s::uuid", (phase_id, unit_id))
            if not cur.fetchone():
                raise LookupError("phase_not_found")

            # Resolve current phase placement for all requested modules.
            cur.execute(
                """
                select um.id::text, um.phase_id::text
                  from public.unit_modules um
                 where um.unit_id = %s::uuid
                   and um.id = any(%s::uuid[])
                """,
                (unit_id, module_ids),
            )
            rows = cur.fetchall() or []
            if len(rows) != len(module_ids):
                raise LookupError("module_not_in_unit")
            original_phase_by_module = {r[0]: r[1] for r in rows}
            desired_set = set(module_ids)

            # Append existing modules in the target phase that are not mentioned.
            cur.execute(
                """
                select um.id::text
                  from public.unit_modules um
                  join public.unit_phases p on p.id = um.phase_id
                 where um.unit_id = %s::uuid
                   and um.phase_id = %s::uuid
                 order by um.position_in_phase asc, um.id asc
                """,
                (unit_id, phase_id),
            )
            existing_in_phase = [r[0] for r in (cur.fetchall() or [])]
            extras = [mid for mid in existing_in_phase if mid not in desired_set]
            full_order = list(module_ids) + extras

            # Deferrable unique constraint enables transactional reorder updates.
            cur.execute("set constraints unit_modules_phase_id_position_in_phase_key deferred")
            orderings = list(range(1, len(full_order) + 1))
            cur.execute(
                """
                with new_order as (
                  select mid, ord
                    from unnest(%s::uuid[], %s::int[]) as t(mid, ord)
                )
                update public.unit_modules um
                   set phase_id = %s::uuid,
                       position_in_phase = n.ord
                  from new_order n
                 where um.unit_id = %s::uuid
                   and um.id = n.mid
                """,
                (full_order, orderings, phase_id, unit_id),
            )

            # Compact phases that lost moved modules (keep stable relative order).
            moved_from_phases = sorted(
                {original_phase_by_module[mid] for mid in module_ids if original_phase_by_module.get(mid) != phase_id}
            )
            for src_phase_id in moved_from_phases:
                cur.execute(
                    """
                    select um.id::text
                      from public.unit_modules um
                     where um.unit_id = %s::uuid
                       and um.phase_id = %s::uuid
                     order by um.position_in_phase asc, um.id asc
                    """,
                    (unit_id, src_phase_id),
                )
                remaining = [r[0] for r in (cur.fetchall() or [])]
                if not remaining:
                    continue
                orderings = list(range(1, len(remaining) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select mid, ord
                        from unnest(%s::uuid[], %s::int[]) as t(mid, ord)
                    )
                    update public.unit_modules um
                       set position_in_phase = n.ord
                      from new_order n
                     where um.unit_id = %s::uuid
                       and um.id = n.mid
                    """,
                    (remaining, orderings, unit_id),
                )

            # Return the updated module list for the target phase.
            cur.execute(
                """
                select um.id::text,
                       um.unit_id::text,
                       um.section_id::text,
                       um.phase_id::text,
                       um.position_in_phase,
                       um.required_prereq_count,
                       s.title
                  from public.unit_modules um
                  join public.unit_sections s on s.id = um.section_id
                 where um.unit_id = %s::uuid
                   and um.phase_id = %s::uuid
                 order by um.position_in_phase asc, um.id asc
                """,
                (unit_id, phase_id),
            )
            out_rows = cur.fetchall() or []
            conn.commit()
    return [
        {
            "id": r[0],
            "unit_id": r[1],
            "section_id": r[2],
            "phase_id": r[3],
            "position_in_phase": int(r[4] or 1),
            "required_prereq_count": int(r[5] or 0),
            "title": r[6],
        }
        for r in out_rows
    ]

def update_unit_module_owned(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    module_id: str,
    author_id: str,
    title=_UNSET,
    required_prereq_count=_UNSET,
) -> Optional[dict]:
    """Update module settings inside a modular unit (author only).

    Option B:
        The visible module title lives on the backing section row
        (`public.unit_sections.title`). The unlock setting
        `required_prereq_count` lives on `public.unit_modules`.

    Parameters:
        unit_id: Modular unit id.
        module_id: Unit module id (graph node).
        author_id: Caller sub; must own the unit.
        title: New title (1..200) or `_UNSET` to keep current title.
        required_prereq_count: New k (>= 0) or `_UNSET` to keep current value.

    Returns:
        Updated module dict (including section_id for internal wiring) or
        None when the module is not visible to the caller.
    """
    if _is_unset(title) and _is_unset(required_prereq_count):
        raise ValueError("empty_payload")

    t: str | None = None
    if not _is_unset(title):
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")

    k: int | None = None
    if not _is_unset(required_prereq_count):
        if required_prereq_count is None or isinstance(required_prereq_count, bool) or not isinstance(required_prereq_count, int):
            raise ValueError("invalid_required_prereq_count")
        k = int(required_prereq_count)
        if k < 0:
            raise ValueError("invalid_required_prereq_count")

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select um.section_id::text,
                       um.phase_id::text,
                       um.position_in_phase,
                       um.required_prereq_count,
                       s.title
                  from public.unit_modules um
                  join public.unit_sections s on s.id = um.section_id
                 where um.unit_id = %s::uuid
                   and um.id = %s::uuid
                 for update
                """,
                (unit_id, module_id),
            )
            row = cur.fetchone()
            if not row:
                return None

            section_id = row[0]
            phase_id = row[1]
            pos_in_phase = int(row[2] or 1)
            current_k = int(row[3] or 0)
            current_title = str(row[4] or "")

            if t is not None:
                cur.execute(
                    """
                    update public.unit_sections
                    set title = %s
                    where id = %s::uuid
                      and unit_id = %s::uuid
                    """,
                    (t, section_id, unit_id),
                )
                current_title = t

            if k is not None:
                cur.execute(
                    """
                    update public.unit_modules
                    set required_prereq_count = %s
                    where unit_id = %s::uuid
                      and id = %s::uuid
                    """,
                    (k, unit_id, module_id),
                )
                current_k = k

            conn.commit()
    return {
        "id": module_id,
        "unit_id": unit_id,
        "section_id": section_id,
        "phase_id": phase_id,
        "position_in_phase": pos_in_phase,
        "required_prereq_count": current_k,
        "title": current_title,
    }

def _clamp_required_prereq_count_to_incoming(
    *,
    cur,
    unit_id: str,
    target_module_ids: list[str],
) -> None:
    """Clamp k-of-n setting to current incoming edge count for target modules.

    Why:
        Module/phase deletions remove edges via FK cascades. When a removed
        prerequisite was part of a target module's incoming set, the target
        `required_prereq_count` must be reduced to remain in the valid range
        `0..incoming_count`.
    """
    module_ids = sorted({mid for mid in (target_module_ids or []) if mid})
    if not module_ids:
        return
    cur.execute(
        """
        with incoming as (
          select um.id as module_id,
                 coalesce((
                   select count(*)
                   from public.unit_module_edges e
                   where e.unit_id = um.unit_id
                     and e.to_module_id = um.id
                 ), 0)::int as incoming_count
          from public.unit_modules um
          where um.unit_id = %s::uuid
            and um.id = any(%s::uuid[])
        )
        update public.unit_modules um
        set required_prereq_count = least(um.required_prereq_count, incoming.incoming_count)
        from incoming
        where um.unit_id = %s::uuid
          and um.id = incoming.module_id
          and um.required_prereq_count > incoming.incoming_count
        """,
        (unit_id, module_ids, unit_id),
    )

def update_unit_module_title(*, dsn: str, psycopg_module, unit_id: str, module_id: str, title: str, author_id: str) -> Optional[dict]:
    """Rename a module inside a modular unit (author only).

    Option B:
        The visible module title is stored on the backing section row
        (`public.unit_sections.title`). This method updates that title.

    Returns:
        Updated module dict (including section_id for internal wiring) or
        None when the module is not visible to the caller.
    """
    t = (title or "").strip()
    if not t or len(t) > 200:
        raise ValueError("invalid_title")

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select um.section_id::text,
                       um.phase_id::text,
                       um.position_in_phase,
                       um.required_prereq_count
                  from public.unit_modules um
                 where um.unit_id = %s::uuid
                   and um.id = %s::uuid
                 for update
                """,
                (unit_id, module_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            section_id, phase_id, pos_in_phase, req_prereq = row[0], row[1], int(row[2] or 1), int(row[3] or 0)

            cur.execute(
                """
                update public.unit_sections
                set title = %s
                where id = %s::uuid
                  and unit_id = %s::uuid
                """,
                (t, section_id, unit_id),
            )
            conn.commit()
    return {
        "id": module_id,
        "unit_id": unit_id,
        "section_id": section_id,
        "phase_id": phase_id,
        "position_in_phase": pos_in_phase,
        "required_prereq_count": req_prereq,
        "title": t,
    }

def delete_unit_module_for_author(*, dsn: str, psycopg_module, unit_id: str, module_id: str, author_id: str) -> bool:
    """Delete a module and its backing content (author only).

    Option B:
        Deletes the backing section row, which cascades to:
          - unit_modules (via FK on unit_modules.section_id)
          - unit_tasks/unit_materials etc. (section-owned content)
          - unit_module_edges (via FK on from/to module ids)

    Additionally resequences remaining modules within the affected phase to
    keep positions contiguous (1..n) for stable edge validation and UX.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select distinct to_module_id::text
                from public.unit_module_edges
                where unit_id = %s::uuid
                  and from_module_id = %s::uuid
                """,
                (unit_id, module_id),
            )
            affected_targets = [r[0] for r in (cur.fetchall() or []) if r and r[0]]

            cur.execute(
                """
                select um.section_id::text, um.phase_id::text
                from public.unit_modules um
                where um.unit_id = %s::uuid
                  and um.id = %s::uuid
                for update
                """,
                (unit_id, module_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            section_id, phase_id = row[0], row[1]

            cur.execute(
                """
                delete from public.unit_sections
                where id = %s::uuid
                  and unit_id = %s::uuid
                """,
                (section_id, unit_id),
            )
            if int(cur.rowcount or 0) == 0:
                return False

            # Keep section positions contiguous (used by linear units; harmless for modular).
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position asc, id) as rn
                  from public.unit_sections
                  where unit_id = %s::uuid
                )
                update public.unit_sections u
                set position = o.rn
                from ordered o
                where u.id = o.id
                """,
                (unit_id,),
            )

            # Resequence remaining modules in the phase (important for edge direction checks).
            cur.execute("set constraints unit_modules_phase_id_position_in_phase_key deferred")
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position_in_phase asc, id) as rn
                  from public.unit_modules
                  where unit_id = %s::uuid
                    and phase_id = %s::uuid
                )
                update public.unit_modules um
                set position_in_phase = o.rn
                from ordered o
                where um.id = o.id
                """,
                (unit_id, phase_id),
            )

            _clamp_required_prereq_count_to_incoming(
                cur=cur,
                unit_id=unit_id,
                target_module_ids=affected_targets,
            )

            conn.commit()
            return True

def delete_unit_phase_for_author(*, dsn: str, psycopg_module, unit_id: str, phase_id: str, author_id: str) -> bool:
    """Delete a phase and all contained modules/edges/content (author only).

    Why:
        Teachers need to restructure a modular unit quickly. Deleting a
        phase should remove all its modules and their content to avoid
        orphaned sections (Option B).

    Behavior:
        - Deletes backing sections for all modules in the phase.
        - Deletes the phase row.
        - Resequences remaining phase positions to keep them contiguous.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select unit_type from public.units where id = %s and author_id = %s for update",
                (unit_id, author_id),
            )
            unit_row = cur.fetchone()
            if not unit_row:
                raise PermissionError("unit_not_found_or_not_owned")
            unit_type = str(unit_row[0] or "linear").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select id::text
                from public.unit_phases
                where id = %s::uuid
                  and unit_id = %s::uuid
                for update
                """,
                (phase_id, unit_id),
            )
            phase_row = cur.fetchone()
            if not phase_row:
                return False

            cur.execute(
                """
                select um.id::text,
                       um.section_id::text
                from public.unit_modules um
                where um.unit_id = %s::uuid
                  and um.phase_id = %s::uuid
                """,
                (unit_id, phase_id),
            )
            rows = cur.fetchall() or []
            module_ids = [r[0] for r in rows if r and r[0]]
            section_ids = [r[1] for r in rows if len(r) > 1 and r[1]]

            affected_targets: list[str] = []
            if module_ids:
                cur.execute(
                    """
                    select distinct to_module_id::text
                    from public.unit_module_edges
                    where unit_id = %s::uuid
                      and from_module_id = any(%s::uuid[])
                    """,
                    (unit_id, module_ids),
                )
                affected_targets = [r[0] for r in (cur.fetchall() or []) if r and r[0]]

            if section_ids:
                cur.execute(
                    """
                    delete from public.unit_sections
                    where unit_id = %s::uuid
                      and id = any(%s::uuid[])
                    """,
                    (unit_id, section_ids),
                )
                # Resequence section positions (linear-only, but keeps unit tidy).
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.unit_sections
                      where unit_id = %s::uuid
                    )
                    update public.unit_sections u
                    set position = o.rn
                    from ordered o
                    where u.id = o.id
                    """,
                    (unit_id,),
                )

            cur.execute(
                """
                delete from public.unit_phases
                where id = %s::uuid
                  and unit_id = %s::uuid
                """,
                (phase_id, unit_id),
            )
            if int(cur.rowcount or 0) == 0:
                return False

            # Resequence remaining phases to keep (unit_id, position) contiguous.
            cur.execute("set constraints unit_phases_unit_id_position_key deferred")
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position asc, id) as rn
                  from public.unit_phases
                  where unit_id = %s::uuid
                )
                update public.unit_phases p
                set position = o.rn
                from ordered o
                where p.id = o.id
                """,
                (unit_id,),
            )

            _clamp_required_prereq_count_to_incoming(
                cur=cur,
                unit_id=unit_id,
                target_module_ids=affected_targets,
            )
            conn.commit()
            return True
