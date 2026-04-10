"""
Server-side store for Browser-BFF token sessions.

Why:
    The SvelteKit BFF needs access and refresh tokens across process restarts
    and multiple replicas. The browser still receives only an opaque session
    id; token material remains server-side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import secrets
import time


def _now() -> int:
    return int(time.time())


@dataclass
class BFFSessionRecord:
    session_id: str
    access_token: str
    refresh_token: str | None
    id_token: str
    expires_at: int


class BFFSessionStore:
    def __init__(self) -> None:
        self._data: Dict[str, BFFSessionRecord] = {}

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
            expires_at=expires_at,
        )
        self._data[session_id] = rec
        return rec

    def get(self, session_id: str) -> Optional[BFFSessionRecord]:
        rec = self._data.get(session_id)
        if not rec:
            return None
        if rec.expires_at <= _now():
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
    ) -> Optional[BFFSessionRecord]:
        if session_id not in self._data:
            return None
        rec = BFFSessionRecord(
            session_id=session_id,
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            expires_at=expires_at,
        )
        self._data[session_id] = rec
        return rec

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)
