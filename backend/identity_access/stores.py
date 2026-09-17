"""In-memory session test double for isolated application tests.

Production session resolution always uses UnifiedSessionRepository and SessionService.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional


def _now() -> int:
    return int(time.time())


@dataclass
class SessionRecord:
    session_id: str
    sub: str
    roles: list[str]
    name: str
    expires_at: Optional[int] = None
    id_token: Optional[str] = None
    ttl_seconds: int = 3600


class SessionStore:
    def __init__(self):
        self._data: Dict[str, SessionRecord] = {}

    def update_display_name(self, sub: str, name: str) -> None:
        for record in self._data.values():
            if record.sub == sub:
                record.name = name

    def create(self, *, sub: str, roles: list[str], name: str, ttl_seconds: int = 3600, id_token: Optional[str] = None) -> SessionRecord:
        sid = secrets.token_urlsafe(24)
        rec = SessionRecord(
            session_id=sid,
            sub=sub,
            roles=roles,
            name=name,
            expires_at=_now() + ttl_seconds,
            id_token=id_token,
            ttl_seconds=ttl_seconds,
        )
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
