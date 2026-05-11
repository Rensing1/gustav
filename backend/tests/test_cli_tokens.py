from __future__ import annotations

from identity_access.cli_tokens import InMemoryCLITokenStore
from identity_access.cli_tokens import DBCLITokenStore


def test_cli_token_create_returns_raw_token_once_and_stores_only_hash() -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)

    created = store.create_token(
        user_sub="teacher-1",
        label="Laptop",
        scopes=["read"],
        ttl_seconds=60,
    )

    assert created.raw_token.startswith("gustav_cli_")
    assert created.record.label == "Laptop"
    assert created.record.user_sub == "teacher-1"
    assert created.record.scopes == ["read"]
    assert created.record.expires_at == 1_060
    assert created.record.token_hash
    assert created.raw_token not in created.record.token_hash

    listed = store.list_tokens("teacher-1")
    assert len(listed) == 1
    assert not hasattr(listed[0], "raw_token")


def test_cli_token_create_normalizes_label() -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)

    created = store.create_token(
        user_sub="teacher-1",
        label="  Laptop  ",
        scopes=["read"],
        ttl_seconds=60,
    )

    assert created.record.label == "Laptop"


def test_cli_token_create_rejects_invalid_scopes() -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)

    try:
        store.create_token(
            user_sub="teacher-1",
            label="Laptop",
            scopes=["admin"],
            ttl_seconds=60,
        )
    except ValueError as exc:
        assert str(exc) == "invalid_cli_token_scopes"
        return
    raise AssertionError("invalid scope was accepted")


def test_cli_token_verify_enforces_scope_expiry_and_revocation() -> None:
    now = {"value": 1_000}
    store = InMemoryCLITokenStore(now=lambda: now["value"])
    created = store.create_token(
        user_sub="teacher-1",
        label="Laptop",
        scopes=["read"],
        ttl_seconds=60,
    )

    verified = store.verify_token(created.raw_token, required_scope="read")
    assert verified is not None
    assert verified.user_sub == "teacher-1"

    assert store.verify_token(created.raw_token, required_scope="write") is None

    now["value"] = 1_061
    assert store.verify_token(created.raw_token, required_scope="read") is None

    now["value"] = 1_010
    assert store.revoke_token(user_sub="teacher-1", token_id=created.record.id)
    assert store.verify_token(created.raw_token, required_scope="read") is None


def test_cli_token_revoke_is_limited_to_owner() -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    created = store.create_token(
        user_sub="teacher-1",
        label="Laptop",
        scopes=["read"],
        ttl_seconds=60,
    )

    assert not store.revoke_token(user_sub="teacher-2", token_id=created.record.id)
    assert store.verify_token(created.raw_token, required_scope="read") is not None


def test_cli_token_last_used_is_throttled() -> None:
    now = {"value": 1_000}
    store = InMemoryCLITokenStore(now=lambda: now["value"], last_used_throttle_seconds=900)
    created = store.create_token(
        user_sub="teacher-1",
        label="Laptop",
        scopes=["read"],
        ttl_seconds=3_600,
    )

    assert store.verify_token(created.raw_token, required_scope="read") is not None
    assert store.list_tokens("teacher-1")[0].last_used_at == 1_000

    now["value"] = 1_100
    assert store.verify_token(created.raw_token, required_scope="read") is not None
    assert store.list_tokens("teacher-1")[0].last_used_at == 1_000

    now["value"] = 2_000
    assert store.verify_token(created.raw_token, required_scope="read") is not None
    assert store.list_tokens("teacher-1")[0].last_used_at == 2_000


def test_db_cli_token_store_rejects_unsafe_table_name() -> None:
    try:
        DBCLITokenStore(dsn="postgresql://example", table="public.cli_tokens;drop")
    except RuntimeError:
        # psycopg may be absent in stripped-down environments. Table validation
        # is still covered wherever the optional dependency is installed.
        return
    except ValueError as exc:
        assert str(exc) == "Invalid table name"
        return
    raise AssertionError("unsafe table name was accepted")
