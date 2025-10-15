"""
In-memory stores for development: StateStore and SessionStore.

Why: Keep server-side state (CSRF/QR context, PKCE code_verifier) and sessions
opaque to the client. For production, replace with Redis/DB-backed stores.

Security: Cookies carry only an opaque session id. Session data stays server-side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import secrets
import time


def _now() -> int:
    return int(time.time())


@dataclass
class StateRecord:
    state: str
    code_verifier: str
    redirect: Optional[str]
    expires_at: int


class StateStore:
    def __init__(self):
        self._data: Dict[str, StateRecord] = {}

    def create(self, *, code_verifier: str, ttl_seconds: int = 900, redirect: Optional[str] = None) -> StateRecord:
        state = secrets.token_urlsafe(24)
        rec = StateRecord(state=state, code_verifier=code_verifier, redirect=redirect, expires_at=_now() + ttl_seconds)
        self._data[state] = rec
        return rec

    def pop_valid(self, state: str) -> Optional[StateRecord]:
        rec = self._data.pop(state, None)
        if not rec:
            return None
        if rec.expires_at < _now():
            return None
        return rec


@dataclass
class SessionRecord:
    session_id: str
    email: str
    roles: list[str]
    email_verified: bool
    expires_at: Optional[int] = None


class SessionStore:
    def __init__(self):
        self._data: Dict[str, SessionRecord] = {}

    def create(self, *, email: str, roles: list[str], email_verified: bool, ttl_seconds: int = 3600) -> SessionRecord:
        sid = secrets.token_urlsafe(24)
        rec = SessionRecord(session_id=sid, email=email, roles=roles, email_verified=email_verified, expires_at=_now() + ttl_seconds)
        self._data[sid] = rec
        return rec

    def get(self, session_id: str) -> Optional[SessionRecord]:
        rec = self._data.get(session_id)
        if not rec:
            return None
        if rec.expires_at and rec.expires_at < _now():
            self._data.pop(session_id, None)
            return None
        return rec

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)

