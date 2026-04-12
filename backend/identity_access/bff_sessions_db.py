"""
Database-backed store for Browser-BFF token sessions.

Why:
    Browser-BFF sessions must survive process restarts and scale across
    multiple frontend instances while keeping token material off the browser.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import time

try:
    import psycopg
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False


def _now() -> int:
    return int(time.time())


def _default_ttl_seconds() -> int:
    raw = (os.getenv("BFF_SESSION_TTL_SECONDS") or os.getenv("APP_SESSION_TTL_SECONDS") or "").strip()
    default_seconds = 24 * 60 * 60
    try:
        value = int(raw) if raw else default_seconds
    except ValueError:
        value = default_seconds
    return max(15 * 60, min(value, 7 * 24 * 60 * 60))


@dataclass
class BFFSessionRecord:
    session_id: str
    access_token: str
    refresh_token: str | None
    id_token: str
    access_token_expires_at: int
    session_expires_at: int

    @property
    def expires_at(self) -> int:
        return self.access_token_expires_at


class DBBFFSessionStore:
    def __init__(
        self,
        dsn: str | None = None,
        table: str = "public.bff_sessions",
        default_ttl_seconds: int | None = None,
    ) -> None:
        if not HAVE_PSYCOPG:
            raise RuntimeError("psycopg3 is required for DBBFFSessionStore")
        self._dsn = (
            dsn
            or os.getenv("SESSION_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DB_URL", "")
        )
        if not self._dsn:
            raise RuntimeError("No database DSN provided for DBBFFSessionStore")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,62}(?:\.[A-Za-z_][A-Za-z0-9_]{0,62})?$", table or ""):
            raise ValueError("Invalid table name")
        self._table = table
        self._default_ttl_seconds = default_ttl_seconds or _default_ttl_seconds()

    def _schema_and_name(self) -> tuple[str, str]:
        if "." in self._table:
            return tuple(self._table.split(".", 1))  # type: ignore[return-value]
        return ("public", self._table)

    def create(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        id_token: str,
        expires_at: int,
    ) -> BFFSessionRecord:
        session_expires_at = _now() + self._default_ttl_seconds
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                try:
                    from psycopg import sql as _sql  # type: ignore

                    schema, name_tbl = self._schema_and_name()
                    stmt = _sql.SQL(
                        "insert into {}.{} (session_id, access_token, refresh_token, id_token, expires_at, access_token_expires_at, session_expires_at) "
                        "values (gen_random_uuid()::text, %s, %s, %s, to_timestamp(%s), to_timestamp(%s), to_timestamp(%s)) returning session_id"
                    ).format(_sql.Identifier(schema), _sql.Identifier(name_tbl))
                    cur.execute(
                        stmt,
                        (access_token, refresh_token, id_token, expires_at, expires_at, session_expires_at),
                    )
                except Exception:
                    cur.execute(
                        f"insert into {self._table} (session_id, access_token, refresh_token, id_token, expires_at, access_token_expires_at, session_expires_at) "
                        f"values (gen_random_uuid()::text, %s, %s, %s, to_timestamp(%s), to_timestamp(%s), to_timestamp(%s)) returning session_id",
                        (access_token, refresh_token, id_token, expires_at, expires_at, session_expires_at),
                    )
                row = cur.fetchone()
        return BFFSessionRecord(
            session_id=str((row or [""])[0]),
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            access_token_expires_at=expires_at,
            session_expires_at=session_expires_at,
        )

    def get(self, session_id: str) -> BFFSessionRecord | None:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                try:
                    from psycopg import sql as _sql  # type: ignore

                    schema, name_tbl = self._schema_and_name()
                    stmt = _sql.SQL(
                        "select session_id, access_token, refresh_token, id_token, "
                        "extract(epoch from expires_at)::bigint, "
                        "extract(epoch from access_token_expires_at)::bigint, "
                        "extract(epoch from session_expires_at)::bigint "
                        "from {}.{} where session_id = %s"
                    ).format(_sql.Identifier(schema), _sql.Identifier(name_tbl))
                    cur.execute(stmt, (session_id,))
                except Exception:
                    cur.execute(
                        f"select session_id, access_token, refresh_token, id_token, "
                        f"extract(epoch from expires_at)::bigint, "
                        f"extract(epoch from access_token_expires_at)::bigint, "
                        f"extract(epoch from session_expires_at)::bigint "
                        f"from {self._table} where session_id = %s",
                        (session_id,),
                    )
                row = cur.fetchone()
        if not row:
            return None
        if int(row[6]) <= _now():
            self.delete(session_id)
            return None
        return BFFSessionRecord(
            session_id=str(row[0]),
            access_token=str(row[1]),
            refresh_token=str(row[2]) if row[2] is not None else None,
            id_token=str(row[3]),
            access_token_expires_at=int(row[5]),
            session_expires_at=int(row[6]),
        )

    def update(
        self,
        session_id: str,
        *,
        access_token: str,
        refresh_token: str | None,
        id_token: str,
        expires_at: int,
        session_expires_at: int | None = None,
    ) -> BFFSessionRecord | None:
        current = self.get(session_id)
        if current is None:
            return None
        next_session_expires_at = session_expires_at or current.session_expires_at
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                try:
                    from psycopg import sql as _sql  # type: ignore

                    schema, name_tbl = self._schema_and_name()
                    stmt = _sql.SQL(
                        "update {}.{} set access_token = %s, refresh_token = %s, id_token = %s, "
                        "expires_at = to_timestamp(%s), access_token_expires_at = to_timestamp(%s), "
                        "session_expires_at = to_timestamp(%s) where session_id = %s"
                    ).format(_sql.Identifier(schema), _sql.Identifier(name_tbl))
                    cur.execute(
                        stmt,
                        (
                            access_token,
                            refresh_token,
                            id_token,
                            expires_at,
                            expires_at,
                            next_session_expires_at,
                            session_id,
                        ),
                    )
                except Exception:
                    cur.execute(
                        f"update {self._table} set access_token = %s, refresh_token = %s, id_token = %s, "
                        f"expires_at = to_timestamp(%s), access_token_expires_at = to_timestamp(%s), "
                        f"session_expires_at = to_timestamp(%s) where session_id = %s",
                        (
                            access_token,
                            refresh_token,
                            id_token,
                            expires_at,
                            expires_at,
                            next_session_expires_at,
                            session_id,
                        ),
                    )
        return self.get(session_id)

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
