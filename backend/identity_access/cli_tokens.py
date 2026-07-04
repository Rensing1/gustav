"""Opaque CLI token creation and verification for GUSTAV.

Why:
    CLI tokens let teachers authenticate terminal workflows without putting
    browser session cookies or OIDC refresh tokens into shell scripts. The raw
    token is shown once; stores persist only a hash of the secret part.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import hmac
import os
import re
import secrets
import time
from uuid import uuid4

# Temporary compatibility while legacy tests still import `identity_access.cli_tokens`.
if __name__ == "backend.identity_access.cli_tokens":
    sys.modules.setdefault("identity_access.cli_tokens", sys.modules[__name__])
elif __name__ == "identity_access.cli_tokens":
    sys.modules.setdefault("backend.identity_access.cli_tokens", sys.modules[__name__])
for _parent_name, _attribute_name in (("identity_access", "cli_tokens"), ("backend.identity_access", "cli_tokens")):
    _parent = sys.modules.get(_parent_name)
    if _parent is not None:
        setattr(_parent, _attribute_name, sys.modules[__name__])

try:
    import psycopg
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover - optional dependency in some test envs
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False


_TOKEN_PREFIX = "gustav_cli"
_ALLOWED_SCOPES = {"read", "write", "delete"}


def _now() -> int:
    return int(time.time())


def _hash_secret(secret: str) -> str:
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _parse_raw_token(raw_token: str) -> tuple[str, str] | None:
    parts = raw_token.split("_", 3)
    if len(parts) != 4 or parts[0] != "gustav" or parts[1] != "cli":
        return None
    token_id = parts[2].strip()
    secret = parts[3].strip()
    if not token_id or not secret:
        return None
    return token_id, secret


def _normalize_scopes(scopes: list[str]) -> list[str]:
    normalized = sorted({str(scope).strip() for scope in scopes if str(scope).strip()})
    if not normalized or any(scope not in _ALLOWED_SCOPES for scope in normalized):
        raise ValueError("invalid_cli_token_scopes")
    return normalized


@dataclass(frozen=True)
class CLITokenRecord:
    id: str
    user_sub: str
    label: str
    scopes: list[str]
    token_hash: str
    created_at: int
    expires_at: int
    last_used_at: int | None = None
    revoked_at: int | None = None


@dataclass(frozen=True)
class CreatedCLIToken:
    raw_token: str
    record: CLITokenRecord


class InMemoryCLITokenStore:
    """Small test-friendly CLI token store.

    Production uses a DB-backed variant, but the in-memory implementation keeps
    the token semantics independently testable and documents the expected store
    contract for route adapters.
    """

    def __init__(self, *, now=_now, last_used_throttle_seconds: int = 15 * 60) -> None:
        self._now = now
        self._last_used_throttle_seconds = last_used_throttle_seconds
        self._records: dict[str, CLITokenRecord] = {}

    def create_token(
        self,
        *,
        user_sub: str,
        label: str,
        scopes: list[str],
        ttl_seconds: int,
    ) -> CreatedCLIToken:
        token_id = str(uuid4())
        secret = secrets.token_urlsafe(32)
        raw_token = f"{_TOKEN_PREFIX}_{token_id}_{secret}"
        now = self._now()
        record = CLITokenRecord(
            id=token_id,
            user_sub=user_sub,
            label=label.strip(),
            scopes=_normalize_scopes(scopes),
            token_hash=_hash_secret(secret),
            created_at=now,
            expires_at=now + int(ttl_seconds),
        )
        self._records[token_id] = record
        return CreatedCLIToken(raw_token=raw_token, record=record)

    def list_tokens(self, user_sub: str) -> list[CLITokenRecord]:
        return [
            record
            for record in sorted(self._records.values(), key=lambda item: item.created_at)
            if record.user_sub == user_sub
        ]

    def revoke_token(self, *, user_sub: str, token_id: str) -> bool:
        record = self._records.get(token_id)
        if record is None or record.user_sub != user_sub:
            return False
        if record.revoked_at is None:
            self._records[token_id] = replace(record, revoked_at=self._now())
        return True

    def verify_token(self, raw_token: str, *, required_scope: str) -> CLITokenRecord | None:
        parsed = _parse_raw_token(raw_token)
        if parsed is None:
            return None
        token_id, secret = parsed
        record = self._records.get(token_id)
        now = self._now()
        if record is None or record.revoked_at is not None or record.expires_at <= now:
            return None
        if required_scope not in record.scopes:
            return None
        if not hmac.compare_digest(record.token_hash, _hash_secret(secret)):
            return None
        if record.last_used_at is None or now - record.last_used_at >= self._last_used_throttle_seconds:
            record = replace(record, last_used_at=now)
            self._records[token_id] = record
        return record


class DBCLITokenStore:
    """Postgres-backed CLI token store.

    Uses a service-role connection for hash lookup. Browser and anon DB clients
    are denied by RLS/revokes in the migration; route handlers expose only
    metadata owned by the current authenticated user.
    """

    def __init__(
        self,
        dsn: str | None = None,
        table: str = "public.cli_tokens",
        *,
        last_used_throttle_seconds: int = 15 * 60,
    ) -> None:
        if not HAVE_PSYCOPG:
            raise RuntimeError("psycopg3 is required for DBCLITokenStore")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,62}(?:\.[A-Za-z_][A-Za-z0-9_]{0,62})?$", table or ""):
            raise ValueError("Invalid table name")
        self._dsn = (
            dsn
            or os.getenv("SESSION_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DB_URL", "")
        )
        if not self._dsn:
            raise RuntimeError("No database DSN provided for DBCLITokenStore")
        self._table = table
        self._last_used_throttle_seconds = last_used_throttle_seconds

    def _schema_and_name(self) -> tuple[str, str]:
        if "." in self._table:
            return tuple(self._table.split(".", 1))  # type: ignore[return-value]
        return ("public", self._table)

    def _stmt(self, template: str):
        try:
            from psycopg import sql as _sql  # type: ignore

            schema, name = self._schema_and_name()
            return _sql.SQL(template).format(_sql.Identifier(schema, name))
        except Exception:
            return template.format(self._table)

    @staticmethod
    def _epoch(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        return int(value)  # type: ignore[arg-type]

    def _record_from_row(self, row: object) -> CLITokenRecord:
        values = list(row)  # type: ignore[arg-type]
        return CLITokenRecord(
            id=str(values[0]),
            user_sub=str(values[1]),
            label=str(values[2]),
            scopes=[str(scope) for scope in (values[3] or [])],
            token_hash=str(values[4]),
            created_at=int(self._epoch(values[5]) or 0),
            expires_at=int(self._epoch(values[6]) or 0),
            last_used_at=self._epoch(values[7]),
            revoked_at=self._epoch(values[8]),
        )

    def create_token(
        self,
        *,
        user_sub: str,
        label: str,
        scopes: list[str],
        ttl_seconds: int,
    ) -> CreatedCLIToken:
        token_id = str(uuid4())
        secret = secrets.token_urlsafe(32)
        raw_token = f"{_TOKEN_PREFIX}_{token_id}_{secret}"
        normalized_scopes = _normalize_scopes(scopes)
        with psycopg.connect(self._dsn, autocommit=True) as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                cur.execute(
                    self._stmt(
                        "insert into {} (id, user_sub, label, token_hash, scopes, expires_at) "
                        "values (%s, %s, %s, %s, %s, now() + (%s * interval '1 second')) "
                        "returning id, user_sub, label, scopes, token_hash, created_at, expires_at, last_used_at, revoked_at"
                    ),
                    (token_id, user_sub, label.strip(), _hash_secret(secret), normalized_scopes, int(ttl_seconds)),
                )
                row = cur.fetchone()
        return CreatedCLIToken(raw_token=raw_token, record=self._record_from_row(row))

    def list_tokens(self, user_sub: str) -> list[CLITokenRecord]:
        with psycopg.connect(self._dsn) as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                cur.execute(
                    self._stmt(
                        "select id, user_sub, label, scopes, token_hash, created_at, expires_at, last_used_at, revoked_at "
                        "from {} where user_sub = %s order by created_at"
                    ),
                    (user_sub,),
                )
                rows = cur.fetchall()
        return [self._record_from_row(row) for row in rows]

    def revoke_token(self, *, user_sub: str, token_id: str) -> bool:
        with psycopg.connect(self._dsn, autocommit=True) as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                cur.execute(
                    self._stmt(
                        "update {} set revoked_at = coalesce(revoked_at, now()) "
                        "where id = %s and user_sub = %s"
                    ),
                    (token_id, user_sub),
                )
                return bool(cur.rowcount)

    def verify_token(self, raw_token: str, *, required_scope: str) -> CLITokenRecord | None:
        parsed = _parse_raw_token(raw_token)
        if parsed is None:
            return None
        token_id, secret = parsed
        with psycopg.connect(self._dsn, autocommit=True) as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                cur.execute(
                    self._stmt(
                        "select id, user_sub, label, scopes, token_hash, created_at, expires_at, last_used_at, revoked_at "
                        "from {} where id = %s and revoked_at is null and expires_at > now()"
                    ),
                    (token_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                record = self._record_from_row(row)
                if required_scope not in record.scopes:
                    return None
                if not hmac.compare_digest(record.token_hash, _hash_secret(secret)):
                    return None
                now = _now()
                if record.last_used_at is None or now - record.last_used_at >= self._last_used_throttle_seconds:
                    cur.execute(self._stmt("update {} set last_used_at = now() where id = %s"), (record.id,))
                    record = replace(record, last_used_at=now)
                return record
