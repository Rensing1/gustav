"""
Database-backed SessionStore for production use (Postgres/Supabase).

Why: In-memory sessions are not durable and do not scale across instances. This
store persists sessions in Postgres (e.g., via Supabase) while keeping the
cookie opaque and PII-minimal (no email stored).

Security:
- Intended to be used with a service role connection string; anon clients must
  not access the `app_sessions` table. RLS is enabled; service role bypasses RLS.
- Only the opaque `session_id` is set in the cookie; all user context stays server-side.

Note: This module uses psycopg3. It is imported only when enabled via
`SESSIONS_BACKEND=db`. Tests can continue to use the in-memory store.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
import os
import time
import re

try:
    import psycopg
    from psycopg.types.json import Json
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover - optional dependency in dev
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False


def _now() -> int:
    return int(time.time())


@dataclass
class SessionRecord:
    session_id: str
    sub: str
    roles: list[str]
    name: str
    expires_at: Optional[int]
    id_token: Optional[str] = None
    ttl_seconds: int = 3600


class DBSessionStore:
    """Postgres-backed session store.

    Parameters
    ----------
    dsn:
        Psycopg3 connection string. Use a service role in Supabase.
    table:
        Fully qualified table name. Defaults to `public.app_sessions`.
    """

    def __init__(self, dsn: str | None = None, table: str = "public.app_sessions") -> None:
        if not HAVE_PSYCOPG:
            raise RuntimeError("psycopg3 is required for DBSessionStore")
        self._dsn = dsn or os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL", "")
        if not self._dsn:
            raise RuntimeError("No database DSN provided for DBSessionStore")
        # Validate table identifier early (defense-in-depth)
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]{0,62}(?:\.[A-Za-z_][A-Za-z0-9_]{0,62})?$', table or ''):
            raise ValueError("Invalid table name")
        self._table = table

    def _schema_and_name(self) -> tuple[str, str]:
        if "." in self._table:
            schema, name = self._table.split(".", 1)
        else:
            schema, name = "public", self._table
        return schema, name

    def create(self, *, sub: str, roles: Sequence[str], name: str, ttl_seconds: int = 3600, id_token: Optional[str] = None) -> SessionRecord:
        expires_at = _now() + ttl_seconds
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Prefer psycopg.sql for safe identifier composition if available
                try:
                    from psycopg import sql as _sql  # type: ignore
                    schema, name_tbl = self._schema_and_name()
                    stmt = _sql.SQL(
                        "insert into {}.{} (session_id, sub, roles, name, id_token, expires_at) "
                        "values (gen_random_uuid()::text, %s, %s, %s, %s, to_timestamp(%s)) returning session_id"
                    ).format(_sql.Identifier(schema), _sql.Identifier(name_tbl))
                    cur.execute(stmt, (sub, Json(list(roles)), name, id_token, expires_at))
                except Exception:
                    # Fallback for environments without psycopg.sql (tests with fake psycopg)
                    cur.execute(
                        f"insert into {self._table} (session_id, sub, roles, name, id_token, expires_at) "
                        f"values (gen_random_uuid()::text, %s, %s, %s, %s, to_timestamp(%s)) returning session_id",
                        (sub, Json(list(roles)), name, id_token, expires_at),
                    )
                row = cur.fetchone()
        sid = str(row[0]) if row else ""
        return SessionRecord(session_id=sid, sub=sub, roles=list(roles), name=name, expires_at=expires_at, id_token=id_token, ttl_seconds=ttl_seconds)

    def get(self, session_id: str) -> Optional[SessionRecord]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                try:
                    from psycopg import sql as _sql  # type: ignore
                    schema, name_tbl = self._schema_and_name()
                    stmt = _sql.SQL(
                        "select session_id, sub, roles, name, id_token, extract(epoch from expires_at)::bigint "
                        "from {}.{} where session_id = %s and expires_at > now()"
                    ).format(_sql.Identifier(schema), _sql.Identifier(name_tbl))
                    cur.execute(stmt, (session_id,))
                except Exception:
                    cur.execute(
                        f"select session_id, sub, roles, name, id_token, extract(epoch from expires_at)::bigint "
                        f"from {self._table} where session_id = %s and expires_at > now()",
                        (session_id,),
                    )
                row = cur.fetchone()
                if not row:
                    return None
                roles = row[2] if isinstance(row[2], list) else []
                return SessionRecord(
                    session_id=row[0],
                    sub=row[1],
                    roles=roles,
                    name=row[3],
                    id_token=row[4],
                    expires_at=int(row[5]) if row[5] is not None else None,
                )

    def delete(self, session_id: str) -> None:
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                try:
                    from psycopg import sql as _sql  # type: ignore
                    schema, name_tbl = self._schema_and_name()
                    stmt = _sql.SQL("delete from {}.{} where session_id = %s").format(
                        _sql.Identifier(schema), _sql.Identifier(name_tbl)
                    )
                    cur.execute(stmt, (session_id,))
                except Exception:
                    cur.execute(f"delete from {self._table} where session_id = %s", (session_id,))
