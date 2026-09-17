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

    @staticmethod
    def _insert_session(conn, sid: str, values: dict, browser_hash: str | None = None):
        conn.execute(
            "insert into public.app_sessions (session_id,sub,roles,name,id_token,access_token,refresh_token,access_expires_at,expires_at,browser_hash) "
            "values (%s,%s,%s,%s,%s,%s,%s,to_timestamp(%s),to_timestamp(%s),%s)",
            (digest(sid), values['sub'], Json(values['roles']), values['name'], values['id_token'],
             values['access_token'], values['refresh_token'], values['access_expires_at'], values['expires_at'], browser_hash),
        )

    def create(self, *, sub, roles, name, id_token, access_token, refresh_token, access_expires_at, expires_at):
        sid = secrets.token_urlsafe(32)
        values = dict(sub=sub, roles=roles, name=name, id_token=id_token, access_token=access_token,
                      refresh_token=refresh_token, access_expires_at=access_expires_at, expires_at=expires_at)
        with self.connect() as conn:
            self._insert_session(conn, sid, values)
        return self.get(sid)

    def complete_flow(self, state: str, browser: str, values: dict, old_sid: str | None = None):
        """Issue credentials only while the claimed browser flow is still live.

        Share the short browser lock with logout. No token I/O occurs here.
        A logout that wins afterwards also removes this new session, even if
        its Set-Cookie response has not reached the browser yet.
        """
        sid, binding = secrets.token_urlsafe(32), digest(browser)
        with self.connect() as conn:
            if old_sid:
                conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", ('session:' + digest(old_sid),))
            conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (binding,))
            flow = conn.execute(
                "delete from public.auth_flows where state_hash=%s and browser_hash=%s "
                "and claimed_at is not null and expires_at>now() and mode!='logout' returning state_hash",
                (digest(state), binding),
            ).fetchone()
            if not flow:
                return None
            self._insert_session(conn, sid, values, binding)
            if old_sid:
                # Retain only a short revocation link for requests carrying the old
                # cookie. Clear credentials; this row can no longer authenticate.
                conn.execute(
                    "update public.app_sessions set access_token=null,refresh_token=null,id_token=null,"
                    "browser_hash=%s,expires_at=now()+interval '15 minutes',"
                    "refresh_version=refresh_version+1,refresh_locked_until=null,retry_after=null where session_id=%s",
                    (binding, digest(old_sid)),
                )
        return self.get(sid)

    def revoke_browser(self, sid: str | None, browser: str | None):
        """Revoke flows and issued sessions, including undelivered replacements.

        The old session's binding covers an expired/replaced browser cookie.
        Ordered locks prevent deadlocks when those two bindings differ.
        """
        with self.connect() as conn:
            # Freeze the old-cookie revocation link before resolving browser locks.
            if sid:
                conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", ('session:' + digest(sid),))
            row = conn.execute("select browser_hash from public.app_sessions where session_id=%s",
                               (digest(sid or ''),)).fetchone()
            bindings = {digest(browser)} if browser else set()
            if row and row['browser_hash']:
                bindings.add(row['browser_hash'])
            for binding in sorted(bindings):
                conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (binding,))
            conn.execute("delete from public.auth_flows where browser_hash=any(%s)", (list(bindings),))
            conn.execute("delete from public.app_sessions where browser_hash=any(%s) or session_id=%s",
                         (list(bindings), digest(sid or '')))

    def delete_expired(self, sid: str, version: int) -> bool:
        """Expire only an unchanged row without an active token renewal owner."""
        with self.connect() as conn:
            result = conn.execute(
                "delete from public.app_sessions where session_id=%s and refresh_version=%s "
                "and expires_at<=clock_timestamp() "
                "and (refresh_locked_until is null or refresh_locked_until<=clock_timestamp())",
                (digest(sid), version),
            )
            return result.rowcount == 1

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
        """Reserve only an unchanged session that still needs token renewal."""
        with self.connect() as conn:
            row = conn.execute(
                "update public.app_sessions set refresh_version=refresh_version+1,refresh_locked_until=now()+interval '10 seconds' "
                "where session_id=%s and refresh_version=%s and expires_at>now() "
                "and access_expires_at<=now()+interval '30 seconds' "
                "and (refresh_locked_until is null or refresh_locked_until<now()) "
                "and (retry_after is null or retry_after<now()) returning refresh_version",
                (digest(sid), version),
            ).fetchone()
        return row['refresh_version'] if row else None

    def finish_refresh(self, sid: str, version: int, values: dict) -> bool:
        """Save only the unchanged reservation; expiry permits takeover, not token loss.

        Advance the version on completion too: readers during the network call
        still hold old tokens and expiry. They must re-read before any mutation.
        If nobody reclaimed an expired lease, saving its rotated token is safe.
        """
        with self.connect() as conn:
            result = conn.execute(
                "update public.app_sessions set sub=%s,roles=%s,name=%s,id_token=%s,access_token=%s,refresh_token=%s,"
                "access_expires_at=to_timestamp(%s),expires_at=to_timestamp(%s),refresh_locked_until=null,retry_after=null,"
                "refresh_version=refresh_version+1 "
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

    def delete(self, sid: str, version: int | None = None) -> bool:
        """Revoke a session; report whether an optional snapshot still owned it."""
        with self.connect() as conn:
            result = conn.execute("delete from public.app_sessions where session_id=%s" +
                         (" and refresh_version=%s" if version is not None else ""),
                         (digest(sid), version) if version is not None else (digest(sid),))
            return result.rowcount == 1

    def create_flow(self, *, browser: str, mode: str, redirect: str | None, code_verifier: str, nonce: str) -> AuthFlow:
        state = secrets.token_urlsafe(32)
        binding = digest(browser)
        with self.connect() as conn:
            # A short per-browser lock bounds parallel flow creation, not token HTTP calls.
            conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (binding,))
            conn.execute("delete from public.auth_flows where expires_at<now()")
            conn.execute("delete from public.app_sessions where access_token is null and expires_at<now()")
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
                "update public.auth_flows set claimed_at=now() where state_hash=%s and browser_hash=%s "
                "and expires_at>now() and claimed_at is null "
                "returning mode,redirect_path,code_verifier,nonce", (digest(state), digest(browser)),
            ).fetchone()
        return AuthFlow(state, row['mode'], row['redirect_path'], row['code_verifier'], row['nonce']) if row else None
