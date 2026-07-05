from __future__ import annotations

import logging

import pytest

from backend.identity_access.admin_client import AdminClient
from backend.identity_access.oidc import OIDCConfig


class _DummyKC:
    def _verify_opt(self) -> bool:
        return False


class _DummyResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


def _cfg() -> OIDCConfig:
    return OIDCConfig(
        base_url="https://kc.example",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="https://app.example/auth/callback",
    )


def test_update_user_logs_status_without_response_body(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    client = AdminClient(_cfg())
    client._kc = _DummyKC()  # type: ignore[attr-defined]
    monkeypatch.setattr(client, "_token", lambda: "admin-token")

    def fake_put(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _DummyResponse(400, '{"error":"invalid","email":"student@example.com"}')

    monkeypatch.setattr("backend.identity_access.admin_client.requests.put", fake_put)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValueError, match="user_update_failed"):
            client.update_user(user_id="student-1", payload={"firstName": "New Name"})

    assert "Keycloak user update failed" in caplog.text
    assert "status=400" in caplog.text
    assert "student@example.com" not in caplog.text
    assert '{"error":"invalid"' not in caplog.text
