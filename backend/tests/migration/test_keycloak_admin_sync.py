from __future__ import annotations

import pytest

from backend.tools import keycloak_admin_sync as mod


def test_ensure_local_kc_base_rejects_remote() -> None:
    with pytest.raises(RuntimeError, match="Refusing non-local Keycloak base"):
        mod._ensure_local_kc_base("https://id.example.com", allow_remote=False)

    mod._ensure_local_kc_base("https://id.localhost", allow_remote=False)


def test_build_admin_client_secret_sql_contains_targets() -> None:
    sql = mod._build_admin_client_secret_sql(
        admin_realm="master",
        admin_client_id="gustav-admin-cli",
        admin_client_secret="LOCAL_SECRET",
    )
    assert "name = 'master'" in sql
    assert "client_id = 'gustav-admin-cli'" in sql
    assert "update client set secret = 'LOCAL_SECRET'" in sql


def test_sync_admin_client_secret_updates_primary_and_master(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_run_docker_psql(*, container: str, db_user: str, db_name: str, sql: str) -> None:
        calls.append({"container": container, "db_user": db_user, "db_name": db_name, "sql": sql})

    monkeypatch.setattr(mod, "_run_docker_psql", fake_run_docker_psql)

    mod._sync_admin_client_secret_via_db(
        keycloak_db_container="gustav-keycloak-db",
        keycloak_db_user="keycloak",
        keycloak_db_name="keycloak",
        admin_realm="gustav",
        admin_client_id="gustav-admin-cli",
        admin_client_secret="SYNC_SECRET",
    )

    assert len(calls) == 2
    assert "name = 'gustav'" in calls[0]["sql"]
    assert "name = 'master'" in calls[1]["sql"]
    for call in calls:
        assert call["container"] == "gustav-keycloak-db"
        assert call["db_user"] == "keycloak"
        assert call["db_name"] == "keycloak"


def test_validate_config_requires_yes_for_reset() -> None:
    cfg = mod.SyncConfig(
        kc_base="https://id.localhost",
        admin_realm="master",
        admin_client_id="gustav-admin-cli",
        admin_client_secret="secret",
        admin_username="admin",
        admin_password="password",
        keycloak_db_container="gustav-keycloak-db",
        keycloak_db_user="keycloak",
        keycloak_db_name="keycloak",
        ca_bundle=".tmp/caddy-root.crt",
        insecure_tls=False,
        timeout_seconds=10.0,
        reset_admin_user=True,
        yes=False,
        allow_remote_kc=False,
    )
    with pytest.raises(RuntimeError, match="requires --yes"):
        mod._validate_config(cfg)


def test_ensure_master_admin_user_reset_flow() -> None:
    class FakeApi:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def token_client_credentials(self, *, realm: str, client_id: str, client_secret: str) -> str:
            self.calls.append(("token_client_credentials", realm))
            assert client_id == "gustav-admin-cli"
            assert client_secret == "sync-secret"
            return "token"

        def find_users_by_username(self, *, realm: str, token: str, username: str) -> list[dict]:
            self.calls.append(("find_users_by_username", realm))
            assert token == "token"
            assert username == "admin"
            return [{"id": "existing-user"}]

        def delete_user(self, *, realm: str, token: str, user_id: str) -> None:
            self.calls.append(("delete_user", user_id))
            assert realm == "master"
            assert token == "token"

        def create_user(self, *, realm: str, token: str, username: str) -> str:
            self.calls.append(("create_user", username))
            assert realm == "master"
            assert token == "token"
            return "new-user"

        def update_user_enabled(self, *, realm: str, token: str, user_id: str) -> None:
            self.calls.append(("update_user_enabled", user_id))

        def reset_password(self, *, realm: str, token: str, user_id: str, password: str) -> None:
            self.calls.append(("reset_password", user_id))
            assert realm == "master"
            assert token == "token"
            assert password == "admin-password"

        def realm_role(self, *, realm: str, token: str, role_name: str) -> dict:
            self.calls.append(("realm_role", role_name))
            assert realm == "master"
            assert token == "token"
            assert role_name == "admin"
            return {"id": "r-admin", "name": "admin"}

        def assign_realm_role(self, *, realm: str, token: str, user_id: str, role_repr: dict) -> None:
            self.calls.append(("assign_realm_role", user_id))
            assert realm == "master"
            assert token == "token"
            assert role_repr["name"] == "admin"

        def verify_password_grant(self, *, realm: str, username: str, password: str, client_id: str = "admin-cli") -> None:
            self.calls.append(("verify_password_grant", username))
            assert realm == "master"
            assert username == "admin"
            assert password == "admin-password"
            assert client_id == "admin-cli"

    api = FakeApi()
    mod._ensure_master_admin_user(
        api=api,  # type: ignore[arg-type]
        admin_client_id="gustav-admin-cli",
        admin_client_secret="sync-secret",
        admin_username="admin",
        admin_password="admin-password",
        reset_admin_user=True,
    )

    steps = [name for name, _ in api.calls]
    assert "delete_user" in steps
    assert "create_user" in steps
    assert "reset_password" in steps
    assert "assign_realm_role" in steps
    assert "verify_password_grant" in steps
    assert "update_user_enabled" not in steps
