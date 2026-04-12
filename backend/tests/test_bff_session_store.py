from __future__ import annotations

from backend.identity_access import bff_sessions as mod


def test_get_keeps_record_refreshable_while_session_is_still_valid(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_now", lambda: 200)
    store = mod.BFFSessionStore()
    record = store.create(
        access_token="expired-access",
        refresh_token="refresh-token",
        id_token="id-token",
        expires_at=100,
    )

    loaded = store.get(record.session_id)

    assert loaded is not None
    assert loaded.access_token == "expired-access"
    assert loaded.access_token_expires_at == 100
    assert loaded.session_expires_at == 86600


def test_get_purges_record_when_session_lifetime_has_elapsed(monkeypatch) -> None:
    now_values = iter([0, 200])
    monkeypatch.setattr(mod, "_now", lambda: next(now_values))
    store = mod.BFFSessionStore(default_ttl_seconds=150)
    record = store.create(
        access_token="expired-access",
        refresh_token="refresh-token",
        id_token="id-token",
        expires_at=100,
    )

    loaded = store.get(record.session_id)

    assert loaded is None
    assert store.get(record.session_id) is None
