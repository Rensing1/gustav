"""Material and upload-intent SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but material authoring mixes enough
    Markdown, file, upload-intent, and ordering queries to deserve a focused DB
    module. The functions here receive the DSN and psycopg module from the facade.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.teaching.repo_row_mappers import (
    MATERIAL_COLUMNS_SQL as _MATERIAL_COLUMNS_SQL,
    material_row_to_dict as _material_row_to_dict,
)

_UNSET = object()


def _is_unset(value: object) -> bool:
    """Return True for this module's sentinel or reloaded material sentinels."""

    if value is _UNSET:
        return True
    if type(value) is object:
        return True
    for module_name in ("backend.teaching.services.materials",):
        module = sys.modules.get(module_name)
        if module is not None and value is getattr(module, "_UNSET", None):
            return True
    return False


def list_materials_for_section_owned(*, dsn: str, psycopg_module, unit_id: str, section_id: str, author_id: str) -> List[dict]:
    """Return ordered markdown materials for a section authored by the caller."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                f"""
                select {_MATERIAL_COLUMNS_SQL}
                from public.unit_materials
                where unit_id = %s
                  and section_id = %s
                order by position asc, id
                """,
                (unit_id, section_id),
            )
            rows = cur.fetchall() or []
    return [_material_row_to_dict(r) for r in rows]

def create_markdown_material(*, dsn: str, psycopg_module, unique_violation_cls, unit_id: str, section_id: str, author_id: str, title: str, body_md: str) -> dict:
    """Create a markdown material at the next position within a section."""
    title = (title or "").strip()
    if not title or len(title) > 200:
        raise ValueError("invalid_title")
    if body_md is None or not isinstance(body_md, str):
        raise ValueError("invalid_body_md")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select id from public.unit_sections where id = %s and unit_id = %s for update",
                (section_id, unit_id),
            )
            sec_row = cur.fetchone()
            if not sec_row:
                raise LookupError("section_not_found")
            cur.execute(
                "select id from public.unit_materials where section_id = %s for update",
                (section_id,),
            )
            cur.execute(
                "select coalesce(max(position), 0) + 1 from public.unit_materials where section_id = %s",
                (section_id,),
            )
            next_pos = int(cur.fetchone()[0])
            row = None
            try:
                cur.execute(
                    f"""
                    insert into public.unit_materials (unit_id, section_id, title, body_md, position)
                    values (%s, %s, %s, %s, %s)
                    returning {_MATERIAL_COLUMNS_SQL}
                    """,
                    (unit_id, section_id, title, body_md, next_pos),
                )
                row = cur.fetchone()
            except Exception as exc:
                sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                if unique_violation_cls and isinstance(exc, unique_violation_cls) or sqlstate == "23505":
                    conn.rollback()
                    with conn.cursor() as cur2:
                        cur2.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                        cur2.execute(
                            "select coalesce(max(position), 0) + 1 from public.unit_materials where section_id = %s",
                            (section_id,),
                        )
                        next_pos = int(cur2.fetchone()[0])
                        cur2.execute(
                            f"""
                            insert into public.unit_materials (unit_id, section_id, title, body_md, position)
                            values (%s, %s, %s, %s, %s)
                            returning {_MATERIAL_COLUMNS_SQL}
                            """,
                            (unit_id, section_id, title, body_md, next_pos),
                        )
                        row = cur2.fetchone()
                else:
                    raise
            if row is None:
                raise RuntimeError("unit_materials insert returned no row")
            conn.commit()
    return _material_row_to_dict(row)

def get_material_owned(*, dsn: str, psycopg_module, unit_id: str, section_id: str, material_id: str, author_id: str) -> Optional[dict]:
    """Fetch a single material enforcing author ownership via RLS."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                f"""
                select {_MATERIAL_COLUMNS_SQL}
                from public.unit_materials
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                """,
                (material_id, unit_id, section_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return _material_row_to_dict(row)


def get_material_owned_in_unit(
    *, dsn: str, psycopg_module, unit_id: str, material_id: str, author_id: str
) -> Optional[dict]:
    """Fetch one material from an authored unit without trusting a section id."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                f"""
                select {_MATERIAL_COLUMNS_SQL}
                  from public.unit_materials
                 where unit_id = %s
                   and id = %s
                """,
                (unit_id, material_id),
            )
            row = cur.fetchone()
    return _material_row_to_dict(row) if row else None

def update_material(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    section_id: str,
    material_id: str,
    author_id: str,
    title=_UNSET,
    body_md=_UNSET,
    alt_text=_UNSET,
) -> Optional[dict]:
    """Update mutable fields (title, body_md, alt_text) for a material owned by the caller."""
    if _is_unset(title) and _is_unset(body_md) and _is_unset(alt_text):
        return get_material_owned(
            dsn=dsn,
            psycopg_module=psycopg_module,
            unit_id=unit_id,
            section_id=section_id,
            material_id=material_id,
            author_id=author_id,
        )
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select kind
                from public.unit_materials
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                for update
                """,
                (material_id, unit_id, section_id),
            )
            kind_row = cur.fetchone()
            if not kind_row:
                return None
            material_kind = kind_row[0]
            updates: List[tuple[str, object]] = []
            if not _is_unset(title):
                if title is None:
                    raise ValueError("invalid_title")
                t = (str(title) or "").strip()
                if not t or len(t) > 200:
                    raise ValueError("invalid_title")
                updates.append(("title", t))
            if not _is_unset(body_md):
                if material_kind not in {"markdown", "simulation"}:
                    raise ValueError("invalid_body_md")
                if body_md is None or not isinstance(body_md, str):
                    raise ValueError("invalid_body_md")
                updates.append(("body_md", body_md))
            if not _is_unset(alt_text):
                if material_kind != "file":
                    raise ValueError("invalid_alt_text")
                if alt_text is None:
                    updates.append(("alt_text", None))
                elif not isinstance(alt_text, str):
                    raise ValueError("invalid_alt_text")
                else:
                    normalized_alt = alt_text.strip()
                    if len(normalized_alt) > 500:
                        raise ValueError("invalid_alt_text")
                    updates.append(("alt_text", normalized_alt or None))
            if not updates:
                cur.execute(
                    f"""
                    select {_MATERIAL_COLUMNS_SQL}
                    from public.unit_materials
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    """,
                    (material_id, unit_id, section_id),
                )
                row = cur.fetchone()
                conn.rollback()
                if not row:
                    return None
                return _material_row_to_dict(row)
            try:
                from psycopg import sql as _sql  # type: ignore

                assignments = []
                params: List[object] = []
                for col, val in updates:
                    assignments.append(_sql.SQL("{} = %s").format(_sql.Identifier(col)))
                    params.append(val)
                params.extend([material_id, unit_id, section_id])
                stmt = _sql.SQL(
                    f"""
                    update public.unit_materials
                    set {{assign}}
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    returning {_MATERIAL_COLUMNS_SQL}
                    """
                ).format(assign=_sql.SQL(", ").join(assignments))
                cur.execute(stmt, params)
            except Exception:
                params = [val for _, val in updates] + [material_id, unit_id, section_id]
                cols = ", ".join([f"{col} = %s" for col, _ in updates])
                cur.execute(
                    f"""
                    update public.unit_materials
                    set {cols}
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    returning {_MATERIAL_COLUMNS_SQL}
                    """,
                    params,
                )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            conn.commit()
    return _material_row_to_dict(row)

def delete_material(*, dsn: str, psycopg_module, unit_id: str, section_id: str, material_id: str, author_id: str) -> bool:
    """Delete a material and resequence remaining positions."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id
                from public.unit_materials
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                for update
                """,
                (material_id, unit_id, section_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute(
                "delete from public.unit_materials where id = %s and unit_id = %s and section_id = %s",
                (material_id, unit_id, section_id),
            )
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position asc, id) as rn
                  from public.unit_materials
                  where section_id = %s
                )
                update public.unit_materials m
                set position = o.rn
                from ordered o
                where m.id = o.id
                """,
                (section_id,),
            )
            conn.commit()
            return True

def create_file_upload_intent(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    section_id: str,
    author_id: str,
    intent_id: str,
    material_id: str,
    storage_key: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    material_kind: str = "file",
    expires_at: datetime,
) -> Dict[str, Any]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select id from public.unit_sections where id = %s and unit_id = %s for update",
                (section_id, unit_id),
            )
            if not cur.fetchone():
                raise LookupError("section_not_found")
            cur.execute(
                """
                insert into public.upload_intents (
                    id, material_id, unit_id, section_id, author_id,
                    storage_key, filename, mime_type, size_bytes, material_kind, expires_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id::text,
                          material_id::text,
                          storage_key,
                          filename,
                          mime_type,
                          size_bytes,
                          material_kind,
                          expires_at,
                          consumed_at
                """,
                (
                    intent_id,
                    material_id,
                    unit_id,
                    section_id,
                    author_id,
                    storage_key,
                    filename,
                    mime_type,
                    size_bytes,
                    material_kind,
                    expires_at,
                ),
            )
            row = cur.fetchone()
            conn.commit()
    return {
        "intent_id": row[0],
        "material_id": row[1],
        "storage_key": row[2],
        "filename": row[3],
        "mime_type": row[4],
        "size_bytes": int(row[5]),
        "material_kind": row[6],
        "expires_at": row[7],
        "consumed_at": row[8],
    }

def get_upload_intent_owned(
    *,
    dsn: str,
    psycopg_module,
    intent_id: str,
    unit_id: str,
    section_id: str,
    author_id: str,
) -> Optional[Dict[str, Any]]:
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text,
                       material_id::text,
                       storage_key,
                       filename,
                       mime_type,
                       size_bytes,
                       material_kind,
                       expires_at,
                       consumed_at
                from public.upload_intents
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                  and author_id = %s
                """,
                (intent_id, unit_id, section_id, author_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "intent_id": row[0],
        "material_id": row[1],
        "storage_key": row[2],
        "filename": row[3],
        "mime_type": row[4],
        "size_bytes": int(row[5]),
        "material_kind": row[6],
        "expires_at": row[7],
        "consumed_at": row[8],
    }

def finalize_upload_intent_create_material(
    *,
    dsn: str,
    psycopg_module,
    intent_id: str,
    unit_id: str,
    section_id: str,
    author_id: str,
    title: str,
    alt_text: Optional[str],
    body_md: str = "",
    sha256: str,
) -> Tuple[Dict[str, Any], bool]:
    now = datetime.now(timezone.utc)
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text,
                       material_id::text,
                       storage_key,
                       filename,
                       mime_type,
                       size_bytes,
                       material_kind,
                       expires_at,
                       consumed_at
                from public.upload_intents
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                  and author_id = %s
                for update
                """,
                (intent_id, unit_id, section_id, author_id),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError("intent_not_found")
            (
                _intent_id,
                material_id,
                storage_key,
                filename,
                mime_type,
                size_bytes,
                material_kind,
                expires_at,
                consumed_at,
            ) = row
            if consumed_at is not None:
                cur.execute(
                    f"""
                    select {_MATERIAL_COLUMNS_SQL}
                    from public.unit_materials
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    """,
                    (material_id, unit_id, section_id),
                )
                material_row = cur.fetchone()
                if not material_row:
                    raise LookupError("material_not_found")
                conn.rollback()
                return _material_row_to_dict(material_row), False
            if expires_at <= now:
                raise ValueError("intent_expired")
            cur.execute(
                "select id from public.unit_sections where id = %s and unit_id = %s for update",
                (section_id, unit_id),
            )
            cur.execute(
                "select coalesce(max(position), 0) + 1 from public.unit_materials where section_id = %s",
                (section_id,),
            )
            next_pos = int(cur.fetchone()[0])
            cur.execute(
                f"""
                insert into public.unit_materials (
                    id, unit_id, section_id, title, body_md, position, kind,
                    storage_key, filename_original, mime_type, size_bytes, sha256, alt_text
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning {_MATERIAL_COLUMNS_SQL}
                """,
                (
                    material_id,
                    unit_id,
                    section_id,
                    title,
                    body_md,
                    next_pos,
                    material_kind,
                    storage_key,
                    filename,
                    mime_type,
                    size_bytes,
                    sha256,
                    alt_text,
                ),
            )
            material_row = cur.fetchone()
            cur.execute(
                "update public.upload_intents set consumed_at = %s where id = %s",
                (now, intent_id),
            )
            conn.commit()
    return _material_row_to_dict(material_row), True

def reorder_section_materials(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    section_id: str,
    author_id: str,
    material_ids: List[str],
) -> List[dict]:
    """Atomically reorder materials of a section owned by the caller."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text
                from public.unit_materials
                where unit_id = %s
                  and section_id = %s
                order by position asc, id
                """,
                (unit_id, section_id),
            )
            existing = [row[0] for row in (cur.fetchall() or [])]
            if not existing:
                raise ValueError("material_mismatch")
            existing_set = set(existing)
            submitted_set = set(material_ids)
            if submitted_set != existing_set or len(material_ids) != len(existing):
                extra = submitted_set - existing_set
                if extra:
                    cur.execute(
                        "select count(*) from public.unit_materials where id = any(%s)",
                        (list(extra),),
                    )
                    count = cur.fetchone()
                    if count and int(count[0]) > 0:
                        raise LookupError("material_not_in_section")
                raise ValueError("material_mismatch")
            cur.execute("set constraints unit_materials_section_id_position_key deferred")
            orderings = list(range(1, len(material_ids) + 1))
            cur.execute(
                """
                with new_order as (
                  select mid, ord from unnest(%s::uuid[], %s::int[]) as t(mid, ord)
                )
                update public.unit_materials m
                set position = n.ord
                from new_order n
                where m.id = n.mid
                  and m.section_id = %s
                  and m.unit_id = %s
                """,
                (material_ids, orderings, section_id, unit_id),
            )
            cur.execute(
                """
                select id::text,
                       unit_id::text,
                       section_id::text,
                       title,
                       body_md,
                       position,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                from public.unit_materials
                where unit_id = %s
                  and section_id = %s
                order by position asc, id
                """,
                (unit_id, section_id),
            )
            rows = cur.fetchall() or []
            conn.commit()
    return [
        {
            "id": r[0],
            "unit_id": r[1],
            "section_id": r[2],
            "title": r[3],
            "body_md": r[4],
            "position": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]
