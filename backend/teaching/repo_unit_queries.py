"""Unit SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but unit list/create/update/delete
    and existence checks form a distinct database surface. The functions here
    receive the DSN and psycopg module from the facade.
"""

from __future__ import annotations

from typing import List, Optional


_UNSET = object()


def _is_unset(value: object) -> bool:
    """Accept unset sentinels from DBTeachingRepo and this module."""
    if value is _UNSET:
        return True
    return value.__class__ is object


def list_units_for_author(*, dsn: str, psycopg_module, author_id: str, limit: int, offset: int) -> List[dict]:
    """Return units authored by `author_id` with pagination (teacher scope)."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text,
                       unit_type,
                       title,
                       summary,
                       author_id,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.units
                where author_id = %s
                order by created_at desc, id
                limit %s offset %s
                """,
                (author_id, int(limit), int(offset)),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "unit_type": r[1],
            "title": r[2],
            "summary": r[3],
            "author_id": r[4],
            "created_at": r[5],
            "updated_at": r[6],
        }
        for r in rows
    ]

def create_unit(*, dsn: str, psycopg_module, title: str, summary: Optional[str], author_id: str, unit_type: Optional[str] = None) -> dict:
    """
    Persist a unit for the given author.

    Behavior:
        - Enforces simple validation (non-empty title, summary length).
        - Sets RLS context so only the author can mutate the row.
    """
    norm_type = (unit_type or "linear").strip().lower()
    if norm_type not in {"linear", "modular"}:
        raise ValueError("invalid_unit_type")
    title = (title or "").strip()
    if not title or len(title) > 200:
        raise ValueError("invalid_title")
    if summary is not None:
        summary = summary.strip()
        if summary and len(summary) > 2000:
            raise ValueError("invalid_summary")
        if summary == "":
            summary = None
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                insert into public.units (unit_type, title, summary, author_id)
                values (%s, %s, %s, %s)
                returning id::text,
                          unit_type,
                          title,
                          summary,
                          author_id,
                          to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                          to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                """,
                (norm_type, title, summary, author_id),
            )
            row = cur.fetchone()
            # Modular units require at least one phase. Create a default Phase 1
            # to keep the API usable even before a dedicated phase editor exists.
            if row and norm_type == "modular":
                cur.execute(
                    """
                    insert into public.unit_phases (unit_id, title, position)
                    values (%s::uuid, %s, %s)
                    """,
                    (row[0], "Phase 1", 1),
                )
            conn.commit()
    return {
        "id": row[0],
        "unit_type": row[1],
        "title": row[2],
        "summary": row[3],
        "author_id": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }

def update_unit_owned(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    author_id: str,
    title=_UNSET,
    summary=_UNSET,
) -> Optional[dict]:
    """
    Update fields of a unit when the caller is the author.

    Parameters:
        unit_id: Target unit identifier.
        author_id: Expected author (used for RLS + WHERE clause).
        title/summary: Optional updates; omitted values remain unchanged.
    """
    sets = []
    params: list = []
    if not _is_unset(title):
        if title is None:
            raise ValueError("invalid_title")
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")
        sets.append(("title", t))
    if not _is_unset(summary):
        if summary is None:
            sets.append(("summary", None))
        else:
            s = summary.strip()
            if s and len(s) > 2000:
                raise ValueError("invalid_summary")
            sets.append(("summary", s or None))
    if not sets:
        return get_unit_for_author(dsn=dsn, psycopg_module=psycopg_module, unit_id=unit_id, author_id=author_id)
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            try:
                from psycopg import sql as _sql  # type: ignore

                assignments = []
                params = []
                for col, val in sets:
                    assignments.append(_sql.SQL("{} = %s").format(_sql.Identifier(col)))
                    params.append(val)
                params.extend([unit_id, author_id])
                stmt = _sql.SQL(
                    """
                    update public.units
                    set {assign}
                    where id = %s and author_id = %s
                    returning id::text,
                             unit_type,
                             title,
                             summary,
                             author_id,
                             to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                             to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """
                ).format(assign=_sql.SQL(", ").join(assignments))
                cur.execute(stmt, params)
            except Exception:
                params = [val for _, val in sets] + [unit_id, author_id]
                cols = ", ".join([f"{col} = %s" for col, _ in sets])
                cur.execute(
                    f"""
                    update public.units
                    set {cols}
                    where id = %s and author_id = %s
                    returning id::text,
                             unit_type,
                             title,
                             summary,
                             author_id,
                             to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                             to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    params,
                )
            row = cur.fetchone()
            if not row:
                return None
            conn.commit()
    return {
        "id": row[0],
        "unit_type": row[1],
        "title": row[2],
        "summary": row[3],
        "author_id": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }

def get_unit_for_author(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> Optional[dict]:
    """Fetch a unit enforcing author ownership through RLS."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text,
                       unit_type,
                       title,
                       summary,
                       author_id,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.units
                where id = %s
                """,
                (unit_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
    return {
        "id": row[0],
        "unit_type": row[1],
        "title": row[2],
        "summary": row[3],
        "author_id": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }

def delete_unit_owned(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> bool:
    """Delete a unit owned by `author_id` (RLS + explicit ownership guard)."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "delete from public.units where id = %s and author_id = %s",
                (unit_id, author_id),
            )
            conn.commit()
            return cur.rowcount > 0

def unit_exists_for_author(*, dsn: str, psycopg_module, unit_id: str, author_id: str) -> bool:
    """Check whether the unit exists and is owned by `author_id` via SECURITY DEFINER helper."""
    try:
        with psycopg_module.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select public.unit_exists_for_author(%s, %s)", (author_id, unit_id))
                r = cur.fetchone()
                if r is not None:
                    return bool(r[0])
    except Exception:
        pass
    return get_unit_for_author(dsn=dsn, psycopg_module=psycopg_module, unit_id=unit_id, author_id=author_id) is not None

def unit_exists(*, dsn: str, psycopg_module, unit_id: str) -> Optional[bool]:
    """Check existence (ignoring ownership) using SECURITY DEFINER helper."""
    try:
        with psycopg_module.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select public.unit_exists(%s)", (unit_id,))
                r = cur.fetchone()
                if r is not None:
                    return bool(r[0])
    except Exception:
        return None
    return None

# --- Unit phases (modular units) -----------------------------------------
