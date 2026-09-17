"""Framework-independent session resolution with bounded refresh ownership.

Invalid credentials and unavailable infrastructure are different outcomes.
A temporary outage must never delete a still recoverable user session.
"""
from __future__ import annotations

import time


class SessionUnavailable(Exception):
    """Authentication cannot currently be checked; retain the session."""


class SessionInvalid(Exception):
    """The identity provider definitively rejected the session."""


class SessionService:
    """Resolve an opaque cookie through the shared repository and OIDC adapter."""

    def __init__(self, repository, oidc, validate_tokens):
        self.repository = repository
        self.oidc = oidc
        self.validate_tokens = validate_tokens

    def get(self, sid):
        try:
            return self._resolve(sid)
        except (SessionUnavailable, SessionInvalid):
            raise
        except Exception as exc:
            raise SessionUnavailable() from exc

    def _resolve(self, sid):
        deadline = time.monotonic() + 6
        while True:
            current = self.repository.get(sid)
            if current is None:
                return None
            now = time.time()
            if current.expires_at <= now:
                if self.repository.delete_expired(sid, current.refresh_version):
                    return None
                # A refresh may still own this row or have extended its expiry.
                if time.monotonic() >= deadline:
                    raise SessionUnavailable()
                time.sleep(0.05)
                continue
            if current.access_expires_at > now + 30:
                return current
            version = self.repository.reserve_refresh(sid, current.refresh_version)
            if version is not None:
                try:
                    tokens = self.oidc.refresh_tokens(current.refresh_token)
                    values = self.validate_tokens(tokens, current)
                    self.repository.finish_refresh(sid, version, values)
                except SessionInvalid:
                    self.repository.delete(sid, version)
                    # A stale rejection may not reject credentials saved by a newer owner.
                    if self.repository.get(sid) is None:
                        return None
                    if time.monotonic() >= deadline:
                        raise SessionUnavailable()
                    continue
                except Exception as exc:
                    self.repository.postpone_refresh(sid, version)
                    # Logout or another refresh may have changed the record during I/O.
                    updated = self.repository.get(sid)
                    if updated is None or updated.access_expires_at > time.time():
                        return updated
                    raise SessionUnavailable() from exc
                # Re-read: logout or a newer lease may have won while HTTP was in flight.
                updated = self.repository.get(sid)
                if updated is None or updated.access_expires_at > time.time():
                    return updated
                if time.monotonic() >= deadline:
                    raise SessionUnavailable()
                continue
            if current.access_expires_at > now:
                return current
            if current.retry_after > now or time.monotonic() >= deadline:
                raise SessionUnavailable()
            time.sleep(0.05)

    def update_display_name(self, sub: str, name: str) -> None:
        """Keep the local profile projection current without another token exchange."""
        try:
            self.repository.update_display_name(sub, name)
        except Exception as exc:
            raise SessionUnavailable() from exc

    def delete(self, sid):
        self.repository.delete(sid)
