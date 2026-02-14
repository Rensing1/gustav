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
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if "/roles/student/users" in str(url):
            return _Resp(
                200,
                [
                    {"id": "sub-a", "email": "max.mustermann@example.test", "username": "max.mustermann@example.test"},
                    {"id": "sub-b", "email": "", "username": "legacy-email:anna.von.beispiel@example.test"},
                ],
            )
        if "/roles/default-roles-gustav/users" in str(url):
            return _Resp(200, [])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels(["sub-a", "sub-b", "sub-c"])
    assert out == {
        "sub-a": "max.mustermann",
        "sub-b": "anna.von.beispiel",
        "sub-c": "Unbekannt",
    }
    assert any("/roles/student/users" in url for url in called_urls)
    assert not any("/users/sub-a" in url or "/users/sub-b" in url for url in called_urls)


def test_resolve_student_login_labels_retries_with_admin_fallback_token(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    monkeypatch.setattr(dir._KC, "token_admin_fallback", lambda self: "admin-token")

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        auth = str((headers or {}).get("Authorization", ""))
        if "/roles/student/users" in str(url) and "dummy-token" in auth:
            return _Resp(403, {"error": "forbidden"})
        if "/roles/student/users" in str(url):
            return _Resp(
                200,
                [
                    {"id": "sub-a", "email": "eva.example@example.test", "username": "eva.example@example.test"},
                ],
            )
        if "/roles/default-roles-gustav/users" in str(url):
            return _Resp(200, [])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels(["sub-a", "sub-b"])
    assert out == {"sub-a": "eva.example", "sub-b": "Unbekannt"}
