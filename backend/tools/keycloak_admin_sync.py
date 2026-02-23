"""Synchronize local Keycloak admin credentials with the local environment.

Purpose
-------
Local E2E tests depend on two credential paths at the same time:
- password grant (`admin-cli`, master realm) used by existing E2E fixtures
- confidential client credentials (`KC_ADMIN_CLIENT_*`) used by app runtime

After snapshot restores or realm imports, these credentials can drift from `.env`.
This tool enforces a deterministic local state:
1) Sync confidential client secret in Keycloak DB to `KC_ADMIN_CLIENT_SECRET`.
2) Ensure a master admin user exists and has a known password.
3) Verify password grant works again for the configured admin user.

Security
--------
- Refuses non-local Keycloak base URLs unless `--allow-remote-kc` is set.
- Reset mode (`--reset-admin-user`) requires explicit `--yes`.
- Never logs secrets.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests


LOG = logging.getLogger("gustav.tools.keycloak_admin_sync")

LOCAL_KC_HOSTS = {
    "",
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "id.localhost",
}


@dataclass(frozen=True)
class SyncConfig:
    kc_base: str
    admin_realm: str
    admin_client_id: str
    admin_client_secret: str
    admin_username: str
    admin_password: str
    keycloak_db_container: str
    keycloak_db_user: str
    keycloak_db_name: str
    ca_bundle: str
    insecure_tls: bool
    timeout_seconds: float
    reset_admin_user: bool
    yes: bool
    allow_remote_kc: bool


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _kc_base_default() -> str:
    value = (os.getenv("KC_BASE") or os.getenv("KC_PUBLIC_BASE_URL") or "https://id.localhost").strip()
    return value.rstrip("/")


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_admin_client_secret_sql(*, admin_realm: str, admin_client_id: str, admin_client_secret: str) -> str:
    return f"""
do $$
declare
  rid varchar(36);
  cid varchar(36);
begin
  select id into rid from realm where name = {_sql_literal(admin_realm)};
  if rid is null then
    raise notice 'Keycloak admin realm not found: %', {_sql_literal(admin_realm)};
    return;
  end if;

  select id into cid from client where realm_id = rid and client_id = {_sql_literal(admin_client_id)};
  if cid is null then
    raise notice 'Keycloak admin client not found in realm %: %', {_sql_literal(admin_realm)}, {_sql_literal(admin_client_id)};
    return;
  end if;

  update client set secret = {_sql_literal(admin_client_secret)} where id = cid;
end $$;
"""


def _run_docker_psql(*, container: str, db_user: str, db_name: str, sql: str) -> None:
    subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            db_user,
            "-d",
            db_name,
            "-c",
            sql,
        ],
        check=True,
    )


def _sync_admin_client_secret_via_db(
    *,
    keycloak_db_container: str,
    keycloak_db_user: str,
    keycloak_db_name: str,
    admin_realm: str,
    admin_client_id: str,
    admin_client_secret: str,
) -> None:
    if not admin_client_secret:
        raise RuntimeError("KC_ADMIN_CLIENT_SECRET is required for sync")

    realm_candidates = [admin_realm]
    if admin_realm.strip().lower() != "master":
        realm_candidates.append("master")

    seen: set[str] = set()
    for realm_name in realm_candidates:
        if realm_name in seen:
            continue
        seen.add(realm_name)
        sql = _build_admin_client_secret_sql(
            admin_realm=realm_name,
            admin_client_id=admin_client_id,
            admin_client_secret=admin_client_secret,
        )
        _run_docker_psql(
            container=keycloak_db_container,
            db_user=keycloak_db_user,
            db_name=keycloak_db_name,
            sql=sql,
        )


def _ensure_local_kc_base(kc_base: str, *, allow_remote: bool) -> None:
    host = (urlsplit(kc_base).hostname or "").strip()
    if host in LOCAL_KC_HOSTS:
        return
    if allow_remote:
        LOG.warning("Non-local Keycloak base allowed by flag: host=%s", host)
        return
    raise RuntimeError(
        f"Refusing non-local Keycloak base host={host!r}. "
        "Use --allow-remote-kc only when you know what you are doing."
    )


def _verify_opt(*, ca_bundle: str, insecure_tls: bool):
    if insecure_tls:
        return False
    bundle = (ca_bundle or "").strip()
    if bundle and os.path.exists(bundle):
        return bundle
    return True


class KeycloakAdminApi:
    """Minimal Keycloak admin REST wrapper for local credential synchronization."""

    def __init__(self, *, base_url: str, verify, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.verify = verify

    @staticmethod
    def _admin_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def token_client_credentials(self, *, realm: str, client_id: str, client_secret: str) -> str:
        url = f"{self.base_url}/realms/{realm}/protocol/openid-connect/token"
        resp = self.session.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        resp.raise_for_status()
        token = (resp.json() or {}).get("access_token")
        if not token:
            raise RuntimeError("keycloak_admin_token_missing")
        return str(token)

    def verify_password_grant(self, *, realm: str, username: str, password: str, client_id: str = "admin-cli") -> None:
        url = f"{self.base_url}/realms/{realm}/protocol/openid-connect/token"
        resp = self.session.post(
            url,
            data={
                "grant_type": "password",
                "client_id": client_id,
                "username": username,
                "password": password,
            },
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        resp.raise_for_status()
        if not (resp.json() or {}).get("access_token"):
            raise RuntimeError("keycloak_password_grant_token_missing")

    def find_users_by_username(self, *, realm: str, token: str, username: str) -> list[dict]:
        url = f"{self.base_url}/admin/realms/{realm}/users"
        resp = self.session.get(
            url,
            headers=self._admin_headers(token),
            params={"username": username, "exact": "true"},
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        resp.raise_for_status()
        data = resp.json() or []
        return data if isinstance(data, list) else []

    def delete_user(self, *, realm: str, token: str, user_id: str) -> None:
        url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}"
        resp = self.session.delete(
            url,
            headers=self._admin_headers(token),
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if resp.status_code not in (200, 204):
            resp.raise_for_status()

    def create_user(self, *, realm: str, token: str, username: str) -> str:
        url = f"{self.base_url}/admin/realms/{realm}/users"
        payload = {
            "username": username,
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
        }
        resp = self.session.post(
            url,
            headers=self._admin_headers(token),
            json=payload,
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if resp.status_code not in (201, 204, 409):
            resp.raise_for_status()
        users = self.find_users_by_username(realm=realm, token=token, username=username)
        if not users:
            raise RuntimeError(f"created user {username!r} but lookup returned no id")
        user_id = users[0].get("id")
        if not user_id:
            raise RuntimeError(f"created user {username!r} but response had no id")
        return str(user_id)

    def update_user_enabled(self, *, realm: str, token: str, user_id: str) -> None:
        url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}"
        payload = {
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
        }
        resp = self.session.put(
            url,
            headers=self._admin_headers(token),
            json=payload,
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if resp.status_code not in (200, 204):
            resp.raise_for_status()

    def reset_password(self, *, realm: str, token: str, user_id: str, password: str) -> None:
        url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}/reset-password"
        payload = {"type": "password", "value": password, "temporary": False}
        resp = self.session.put(
            url,
            headers=self._admin_headers(token),
            json=payload,
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if resp.status_code not in (200, 204):
            resp.raise_for_status()

    def realm_role(self, *, realm: str, token: str, role_name: str) -> dict:
        url = f"{self.base_url}/admin/realms/{realm}/roles/{role_name}"
        resp = self.session.get(
            url,
            headers=self._admin_headers(token),
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        if not isinstance(data, dict) or not data.get("name"):
            raise RuntimeError(f"Keycloak role lookup failed for {role_name!r}")
        return data

    def assign_realm_role(self, *, realm: str, token: str, user_id: str, role_repr: dict) -> None:
        url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}/role-mappings/realm"
        resp = self.session.post(
            url,
            headers=self._admin_headers(token),
            json=[role_repr],
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if resp.status_code not in (200, 204):
            resp.raise_for_status()


def _ensure_master_admin_user(
    *,
    api: KeycloakAdminApi,
    admin_client_id: str,
    admin_client_secret: str,
    admin_username: str,
    admin_password: str,
    reset_admin_user: bool,
) -> None:
    token = api.token_client_credentials(
        realm="master",
        client_id=admin_client_id,
        client_secret=admin_client_secret,
    )

    users = api.find_users_by_username(realm="master", token=token, username=admin_username)
    if reset_admin_user and users:
        for user in users:
            user_id = str(user.get("id") or "")
            if not user_id:
                continue
            api.delete_user(realm="master", token=token, user_id=user_id)
        users = []

    if not users:
        user_id = api.create_user(realm="master", token=token, username=admin_username)
    else:
        user_id = str((users[0] or {}).get("id") or "")
        if not user_id:
            raise RuntimeError(f"Keycloak user record missing id for username={admin_username!r}")
        api.update_user_enabled(realm="master", token=token, user_id=user_id)
        if len(users) > 1:
            LOG.warning("Multiple users found for username=%s in master realm; using first record id=%s", admin_username, user_id)

    api.reset_password(realm="master", token=token, user_id=user_id, password=admin_password)
    admin_role = api.realm_role(realm="master", token=token, role_name="admin")
    api.assign_realm_role(realm="master", token=token, user_id=user_id, role_repr=admin_role)
    # Compatibility check for existing E2E fixtures using password grant + admin-cli.
    api.verify_password_grant(realm="master", username=admin_username, password=admin_password, client_id="admin-cli")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync local Keycloak admin credentials with local .env values")
    parser.add_argument("--kc-base", default=_kc_base_default(), help="Browser-facing Keycloak base URL (default from KC_BASE/KC_PUBLIC_BASE_URL)")
    parser.add_argument("--admin-realm", default=os.getenv("KC_ADMIN_REALM", "master"), help="Realm that contains the confidential admin client")
    parser.add_argument("--admin-client-id", default=os.getenv("KC_ADMIN_CLIENT_ID", "gustav-admin-cli"), help="Confidential client ID used for admin API")
    parser.add_argument("--admin-client-secret", default=(os.getenv("KC_ADMIN_CLIENT_SECRET") or "").strip(), help="Confidential client secret to enforce")
    parser.add_argument("--admin-username", default=os.getenv("KEYCLOAK_ADMIN", "admin"), help="Master admin username to ensure")
    parser.add_argument("--admin-password", default=(os.getenv("KEYCLOAK_ADMIN_PASSWORD") or "admin").strip(), help="Master admin password to enforce")
    parser.add_argument("--keycloak-db-container", default=os.getenv("KEYCLOAK_DB_CONTAINER", "gustav-keycloak-db"), help="Docker container name for Keycloak Postgres")
    parser.add_argument("--keycloak-db-user", default=os.getenv("KC_DB_USERNAME", "keycloak"), help="Keycloak Postgres user")
    parser.add_argument("--keycloak-db-name", default=os.getenv("KC_DB_NAME", "keycloak"), help="Keycloak Postgres database")
    parser.add_argument("--ca-bundle", default=os.getenv("KEYCLOAK_CA_BUNDLE", ".tmp/caddy-root.crt"), help="CA bundle for HTTPS verification")
    parser.add_argument("--insecure-tls", action="store_true", help="Disable TLS verification (local fallback only)")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="HTTP timeout for Keycloak API calls")
    parser.add_argument("--reset-admin-user", action="store_true", help="Delete and recreate the configured admin user in master realm")
    parser.add_argument("--yes", action="store_true", help="Required when using --reset-admin-user")
    parser.add_argument("--allow-remote-kc", action="store_true", help="Allow non-local Keycloak base URL (dangerous)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args(argv)


def _build_config(args: argparse.Namespace) -> SyncConfig:
    return SyncConfig(
        kc_base=str(args.kc_base).rstrip("/"),
        admin_realm=str(args.admin_realm),
        admin_client_id=str(args.admin_client_id),
        admin_client_secret=str(args.admin_client_secret),
        admin_username=str(args.admin_username),
        admin_password=str(args.admin_password),
        keycloak_db_container=str(args.keycloak_db_container),
        keycloak_db_user=str(args.keycloak_db_user),
        keycloak_db_name=str(args.keycloak_db_name),
        ca_bundle=str(args.ca_bundle or ""),
        insecure_tls=bool(args.insecure_tls),
        timeout_seconds=float(args.timeout_seconds),
        reset_admin_user=bool(args.reset_admin_user),
        yes=bool(args.yes),
        allow_remote_kc=bool(args.allow_remote_kc),
    )


def _validate_config(cfg: SyncConfig) -> None:
    if not cfg.admin_client_secret:
        raise RuntimeError("Missing KC_ADMIN_CLIENT_SECRET (or --admin-client-secret).")
    if not cfg.admin_username:
        raise RuntimeError("Missing KEYCLOAK_ADMIN (or --admin-username).")
    if not cfg.admin_password:
        raise RuntimeError("Missing KEYCLOAK_ADMIN_PASSWORD (or --admin-password).")
    if cfg.reset_admin_user and not cfg.yes:
        raise RuntimeError("--reset-admin-user requires --yes (explicit acknowledgement).")
    _ensure_local_kc_base(cfg.kc_base, allow_remote=cfg.allow_remote_kc)


def run_sync(cfg: SyncConfig) -> None:
    _validate_config(cfg)

    LOG.info("Syncing Keycloak admin client secret via DB container %s ...", cfg.keycloak_db_container)
    _sync_admin_client_secret_via_db(
        keycloak_db_container=cfg.keycloak_db_container,
        keycloak_db_user=cfg.keycloak_db_user,
        keycloak_db_name=cfg.keycloak_db_name,
        admin_realm=cfg.admin_realm,
        admin_client_id=cfg.admin_client_id,
        admin_client_secret=cfg.admin_client_secret,
    )

    verify_opt = _verify_opt(ca_bundle=cfg.ca_bundle, insecure_tls=cfg.insecure_tls)
    api = KeycloakAdminApi(base_url=cfg.kc_base, verify=verify_opt, timeout_seconds=cfg.timeout_seconds)

    LOG.info("Ensuring master admin user %s is synchronized ...", cfg.admin_username)
    _ensure_master_admin_user(
        api=api,
        admin_client_id=cfg.admin_client_id,
        admin_client_secret=cfg.admin_client_secret,
        admin_username=cfg.admin_username,
        admin_password=cfg.admin_password,
        reset_admin_user=cfg.reset_admin_user,
    )
    LOG.info("Keycloak admin synchronization completed.")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    _configure_logging(args.verbose)
    cfg = _build_config(args)

    try:
        run_sync(cfg)
        return 0
    except Exception as exc:
        LOG.error("Keycloak admin sync failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
