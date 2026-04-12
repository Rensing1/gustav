"""
Server-side store for Browser-BFF token sessions.

Why:
    The SvelteKit BFF needs access and refresh tokens across process restarts
    and multiple replicas. The browser still receives only an opaque session
    id; token material remains server-side.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, Optional
import secrets
import time


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


class BFFSessionStore:
    def __init__(self, default_ttl_seconds: int | None = None) -> None:
        self._data: Dict[str, BFFSessionRecord] = {}
        self._default_ttl_seconds = default_ttl_seconds or _default_ttl_seconds()

    def create(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        id_token: str,
        expires_at: int,
    ) -> BFFSessionRecord:
        session_id = secrets.token_urlsafe(24)
        rec = BFFSessionRecord(
            session_id=session_id,
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            access_token_expires_at=expires_at,
            session_expires_at=_now() + self._default_ttl_seconds,
        )
        self._data[session_id] = rec
        return rec

    def get(self, session_id: str) -> Optional[BFFSessionRecord]:
        rec = self._data.get(session_id)
        if not rec:
            return None
        if rec.session_expires_at <= _now():
            self._data.pop(session_id, None)
            return None
        return rec

    def update(
        self,
        session_id: str,
        *,
        access_token: str,
        refresh_token: str | None,
        id_token: str,
        expires_at: int,
        session_expires_at: int | None = None,
    ) -> Optional[BFFSessionRecord]:
        current = self._data.get(session_id)
        if not current:
            return None
        rec = BFFSessionRecord(
            session_id=session_id,
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            access_token_expires_at=expires_at,
            session_expires_at=session_expires_at or current.session_expires_at,
        )
        self._data[session_id] = rec
        return rec

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)
