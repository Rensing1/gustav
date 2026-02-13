"""
Identity Directory — resolve_student_login_labels returns email localparts.
"""
from __future__ import annotations

import types
import pytest


def _kc_token_stub(self) -> str:  # type: ignore[override]
    return "dummy-token"


class _Resp:
    def __init__(self, status: int, data):
        self.status_code = status
        self._data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def test_resolve_student_login_labels_prefers_email_localpart(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        if url.endswith("/users/sub-a"):
            return _Resp(200, {"email": "max.mustermann@example.test", "username": "max.mustermann@example.test"})
        if url.endswith("/users/sub-b"):
            return _Resp(200, {"email": "", "username": "legacy-email:anna.von.beispiel@example.test"})
        return _Resp(404, {})

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels(["sub-a", "sub-b", "sub-c"])
    assert out == {
        "sub-a": "max.mustermann",
        "sub-b": "anna.von.beispiel",
        "sub-c": "Unbekannt",
    }
