"""PostgreSQL adapter for opaque sessions and browser-bound OIDC flows.

Only the server may use this adapter. Cookie and state secrets are hashed;
refresh ownership is reserved in short transactions, never across HTTP calls.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class TokenSession:
    session_id: str = field(repr=False)
    sub: str
    roles: list[str]
    name: str
    id_token: str = field(repr=False)
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    access_expires_at: float
    expires_at: float
    refresh_version: int = 0
    refresh_locked_until: float = 0
    retry_after: float = 0


@dataclass
class AuthFlow:
    state: str
    mode: str
    redirect: str | None
    code_verifier: str
    nonce: str


class UnifiedSessionRepository:
    """Persist sessions with a dedicated server DSN and bounded connections."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, connect_timeout=5, row_factory=dict_row)

    def create(self, *, sub, roles, name, id_token, access_token, refresh_token, access_expires_at, expires_at):
        sid = secrets.token_urlsafe(32)
        with self.connect() as conn:
            conn.execute(
                "insert into public.app_sessions (session_id,sub,roles,name,id_token,access_token,refresh_token,access_expires_at,expires_at) "
                "values (%s,%s,%s,%s,%s,%s,%s,to_timestamp(%s),to_timestamp(%s))",
                (digest(sid), sub, Json(roles), name, id_token, access_token, refresh_token, access_expires_at, expires_at),
            )
        return self.get(sid)

    def get(self, sid: str) -> TokenSession | None:
        with self.connect() as conn:
            row = conn.execute(
                "select sub,roles,name,id_token,access_token,refresh_token,"
                "extract(epoch from access_expires_at)::float8 as access_expires_at,"
                "extract(epoch from expires_at)::float8 as expires_at,refresh_version,"
                "coalesce(extract(epoch from refresh_locked_until),0)::float8 as refresh_locked_until,"
                "coalesce(extract(epoch from retry_after),0)::float8 as retry_after "
                "from public.app_sessions where session_id=%s and access_token is not null",
                (digest(sid),),
            ).fetchone()
        return TokenSession(session_id=sid, **row) if row else None

    def reserve_refresh(self, sid: str, version: int) -> int | None:
        with self.connect() as conn:
            row = conn.execute(
                "update public.app_sessions set refresh_version=refresh_version+1,refresh_locked_until=now()+interval '10 seconds' "
                "where session_id=%s and refresh_version=%s and expires_at>now() "
                "and (refresh_locked_until is null or refresh_locked_until<now()) "
                "and (retry_after is null or retry_after<now()) returning refresh_version",
                (digest(sid), version),
            ).fetchone()
        return row['refresh_version'] if row else None

    def finish_refresh(self, sid: str, version: int, values: dict) -> bool:
        """Save only the unchanged reservation; expiry permits takeover, not token loss.

        The version fences late owners after takeover or logout. If nobody has
        reclaimed an expired lease, saving its rotated token is still safe.
        """
        with self.connect() as conn:
            result = conn.execute(
                "update public.app_sessions set sub=%s,roles=%s,name=%s,id_token=%s,access_token=%s,refresh_token=%s,"
                "access_expires_at=to_timestamp(%s),expires_at=to_timestamp(%s),refresh_locked_until=null,retry_after=null "
                "where session_id=%s and refresh_version=%s and refresh_locked_until is not null",
                (values['sub'], Json(values['roles']), values['name'], values['id_token'], values['access_token'],
                 values['refresh_token'], values['access_expires_at'], values['expires_at'], digest(sid), version),
            )
            return result.rowcount == 1

    def postpone_refresh(self, sid: str, version: int):
        with self.connect() as conn:
            conn.execute(
                "update public.app_sessions set refresh_locked_until=null,retry_after=now()+interval '5 seconds' "
                "where session_id=%s and refresh_version=%s", (digest(sid), version),
            )

    def update_display_name(self, sub: str, name: str) -> None:
        """Update only the cached display label after an authorized profile change."""
        with self.connect() as conn:
            conn.execute("update public.app_sessions set name=%s where sub=%s", (name, sub))

    def delete(self, sid: str, version: int | None = None):
        with self.connect() as conn:
            conn.execute("delete from public.app_sessions where session_id=%s" +
                         (" and refresh_version=%s" if version is not None else ""),
                         (digest(sid), version) if version is not None else (digest(sid),))

    def create_flow(self, *, browser: str, mode: str, redirect: str | None, code_verifier: str, nonce: str) -> AuthFlow:
        state = secrets.token_urlsafe(32)
        binding = digest(browser)
        with self.connect() as conn:
            # A short per-browser lock bounds parallel flow creation, not token HTTP calls.
            conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (binding,))
            conn.execute("delete from public.auth_flows where expires_at<now()")
            conn.execute(
                "delete from public.auth_flows where state_hash in (select state_hash from public.auth_flows "
                "where browser_hash=%s order by created_at desc offset 2)", (binding,),
            )
            conn.execute(
                "insert into public.auth_flows (state_hash,browser_hash,mode,redirect_path,code_verifier,nonce) values (%s,%s,%s,%s,%s,%s)",
                (digest(state), binding, mode, redirect, code_verifier, nonce),
            )
        return AuthFlow(state, mode, redirect, code_verifier, nonce)

    def consume_flow(self, state: str, browser: str) -> AuthFlow | None:
        with self.connect() as conn:
            row = conn.execute(
                "delete from public.auth_flows where state_hash=%s and browser_hash=%s and expires_at>now() "
                "returning mode,redirect_path,code_verifier,nonce", (digest(state), digest(browser)),
            ).fetchone()
        return AuthFlow(state, row['mode'], row['redirect_path'], row['code_verifier'], row['nonce']) if row else None
