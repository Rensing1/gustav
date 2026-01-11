#!/usr/bin/env python3
"""
Provision a prod-like Keycloak admin client and sync its secret into `.env`.

Goal
----
GUSTAV uses the Keycloak Admin API (server-side) to resolve user display names
and to search for users by role. In production we must *not* rely on the legacy
password grant. Instead, we use a confidential client with `client_credentials`.

This script makes local development behave like production:
  - Ensures a confidential client exists in the `KC_REALM` (default: `gustav`)
    with service accounts enabled.
  - Grants the service-account user the minimal realm-management roles
    (`view-users`, `query-users`) required by our directory adapter.
  - Reads the client secret and writes it into `.env` as `KC_ADMIN_CLIENT_SECRET`.
  - Sets `KC_ADMIN_REALM` to `KC_REALM` (token realm = app realm).

Security & Safety
-----------------
- This is a local-dev helper. It modifies Keycloak configuration.
- It does not print secret values.
- It creates a `.env.bak` backup before writing.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"


def _env_get(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _load_env_file_value(key: str) -> str | None:
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def _update_env(key: str, value: str) -> None:
    if not ENV_PATH.exists():
        raise SystemExit(f"{ENV_PATH} does not exist.")
    lines = ENV_PATH.read_text().splitlines()
    prefix = f"{key}="
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix}{value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{prefix}{value}")
    shutil.copy2(ENV_PATH, ENV_PATH.with_suffix(".bak"))
    ENV_PATH.write_text("\n".join(lines) + "\n")


def _pick_verify() -> bool | str:
    ca = os.getenv("KEYCLOAK_CA_BUNDLE") or _load_env_file_value("KEYCLOAK_CA_BUNDLE") or ""
    ca = ca.strip()
    if ca and Path(ca).exists():
        return ca
    # Fallback for local-only scripts: allow running without a trusted CA.
    return False


def _kc_base_public() -> str:
    # Prefer KC_PUBLIC_BASE_URL (used by the app), then legacy KC_BASE (tests),
    # then default to the reverse-proxy hostname.
    return (
        os.getenv("KC_PUBLIC_BASE_URL")
        or os.getenv("KC_BASE")
        or os.getenv("KC_BASE_URL")
        or "https://id.localhost"
    ).rstrip("/")


def _admin_token(*, base: str, admin_user: str, admin_password: str, verify: bool | str) -> str:
    url = f"{base}/realms/master/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": admin_user,
        "password": admin_password,
    }
    # `docker compose up -d` returns before Keycloak is fully ready. When we call
    # Keycloak through the reverse proxy, the proxy may return 502/503 until
    # Keycloak finishes booting. Retry a short while to avoid flaky local runs.
    ready_timeout_s = int(_env_get("KEYCLOAK_READY_TIMEOUT_S", "60"))
    deadline = time.monotonic() + ready_timeout_s
    last_err: Exception | None = None

    while time.monotonic() < deadline:
        try:
            r = requests.post(url, data=data, timeout=10, verify=verify, allow_redirects=False)
            if r.status_code in (502, 503, 504, 404):
                time.sleep(1)
                continue
            if r.status_code in (401, 403):
                raise SystemExit("Keycloak admin credentials rejected (check KEYCLOAK_ADMIN/_PASSWORD).")
            r.raise_for_status()
            payload = r.json() or {}
            tok = payload.get("access_token")
            if not tok:
                raise SystemExit("Keycloak admin token missing in response.")
            return str(tok)
        except requests.RequestException as exc:
            last_err = exc
            time.sleep(1)

    raise SystemExit(f"Keycloak not ready in {ready_timeout_s}s (admin token request failed). last_err={last_err}")


def _kc_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _kc_get_json(url: str, *, headers: dict[str, str], verify: bool | str) -> Any:
    r = requests.get(url, headers=headers, timeout=15, verify=verify, allow_redirects=False)
    r.raise_for_status()
    return r.json()


def _kc_post_json(url: str, *, headers: dict[str, str], verify: bool | str, payload: Any) -> requests.Response:
    return requests.post(url, headers=headers, json=payload, timeout=15, verify=verify, allow_redirects=False)


def _kc_find_client_uuid(base: str, *, realm: str, token: str, client_id: str, verify: bool | str) -> str | None:
    url = f"{base}/admin/realms/{realm}/clients?clientId={client_id}"
    arr = _kc_get_json(url, headers=_kc_headers(token), verify=verify) or []
    if isinstance(arr, list) and arr:
        cid = arr[0].get("id")
        return str(cid) if cid else None
    return None


def _kc_create_confidential_client(base: str, *, realm: str, token: str, client_id: str, verify: bool | str) -> str:
    url = f"{base}/admin/realms/{realm}/clients"
    payload = {
        "clientId": client_id,
        "name": "GUSTAV Admin (service account)",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "serviceAccountsEnabled": True,
        "standardFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "clientAuthenticatorType": "client-secret",
    }
    r = _kc_post_json(url, headers=_kc_headers(token), verify=verify, payload=payload)
    if r.status_code not in (201, 204):  # KC may return 204 No Content
        r.raise_for_status()
    cid = _kc_find_client_uuid(base, realm=realm, token=token, client_id=client_id, verify=verify)
    if not cid:
        raise SystemExit("Created client but could not resolve its id.")
    return cid


def _kc_get_client_secret(base: str, *, realm: str, token: str, client_uuid: str, verify: bool | str) -> str:
    url = f"{base}/admin/realms/{realm}/clients/{client_uuid}/client-secret"
    data = _kc_get_json(url, headers=_kc_headers(token), verify=verify) or {}
    val = data.get("value")
    if not val:
        raise SystemExit("Client secret missing from Keycloak response.")
    return str(val)


def _kc_get_service_account_user_id(base: str, *, realm: str, token: str, client_uuid: str, verify: bool | str) -> str:
    url = f"{base}/admin/realms/{realm}/clients/{client_uuid}/service-account-user"
    data = _kc_get_json(url, headers=_kc_headers(token), verify=verify) or {}
    uid = data.get("id")
    if not uid:
        raise SystemExit("Service account user id missing (is serviceAccountsEnabled=true?).")
    return str(uid)


def _kc_get_role(base: str, *, realm: str, token: str, client_uuid: str, role_name: str, verify: bool | str) -> dict:
    url = f"{base}/admin/realms/{realm}/clients/{client_uuid}/roles/{role_name}"
    data = _kc_get_json(url, headers=_kc_headers(token), verify=verify)
    if not isinstance(data, dict) or data.get("name") != role_name:
        raise SystemExit(f"Unexpected role representation for {role_name!r}.")
    return data


def _kc_list_client_role_mappings(
    base: str, *, realm: str, token: str, user_id: str, client_uuid: str, verify: bool | str
) -> list[dict]:
    url = f"{base}/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{client_uuid}"
    data = _kc_get_json(url, headers=_kc_headers(token), verify=verify) or []
    return data if isinstance(data, list) else []


def _kc_add_client_role_mappings(
    base: str, *, realm: str, token: str, user_id: str, client_uuid: str, roles: list[dict], verify: bool | str
) -> None:
    if not roles:
        return
    url = f"{base}/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{client_uuid}"
    r = _kc_post_json(url, headers=_kc_headers(token), verify=verify, payload=roles)
    if r.status_code not in (204, 200):
        r.raise_for_status()


def _kc_verify_client_credentials(
    base: str, *, realm: str, client_id: str, client_secret: str, verify: bool | str
) -> None:
    token_url = f"{base}/realms/{realm}/protocol/openid-connect/token"
    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    r = requests.post(token_url, data=data, timeout=10, verify=verify, allow_redirects=False)
    r.raise_for_status()
    tok = (r.json() or {}).get("access_token")
    if not tok:
        raise SystemExit("client_credentials token missing; Keycloak client misconfigured.")

    # Minimal read-only admin API probe
    probe = requests.get(
        f"{base}/admin/realms/{realm}/users?max=1",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=10,
        verify=verify,
        allow_redirects=False,
    )
    if probe.status_code != 200:
        raise SystemExit(f"Admin API probe failed with status {probe.status_code}. Missing roles?")


def main() -> None:
    if not ENV_PATH.exists():
        raise SystemExit(f"{ENV_PATH} not found. Create it (e.g., `cp .env.example .env`) first.")

    kc_base = _kc_base_public()
    verify = _pick_verify()

    realm = _env_get("KC_REALM", "gustav")
    admin_user = _env_get("KEYCLOAK_ADMIN", "admin")
    admin_password = _env_get("KEYCLOAK_ADMIN_PASSWORD", "admin")

    # If someone still uses `admin-cli`, switch to a dedicated confidential client id.
    current_client_id = _env_get("KC_ADMIN_CLIENT_ID", "admin-cli")
    client_id = current_client_id if current_client_id != "admin-cli" else "gustav-admin-cli"

    token = _admin_token(base=kc_base, admin_user=admin_user, admin_password=admin_password, verify=verify)

    client_uuid = _kc_find_client_uuid(kc_base, realm=realm, token=token, client_id=client_id, verify=verify)
    if not client_uuid:
        client_uuid = _kc_create_confidential_client(kc_base, realm=realm, token=token, client_id=client_id, verify=verify)

    # Ensure role mappings for service account user
    realm_mgmt_uuid = _kc_find_client_uuid(kc_base, realm=realm, token=token, client_id="realm-management", verify=verify)
    if not realm_mgmt_uuid:
        raise SystemExit("Keycloak realm-management client not found; unexpected realm state.")

    svc_user_id = _kc_get_service_account_user_id(kc_base, realm=realm, token=token, client_uuid=client_uuid, verify=verify)
    existing = _kc_list_client_role_mappings(kc_base, realm=realm, token=token, user_id=svc_user_id, client_uuid=realm_mgmt_uuid, verify=verify)
    existing_names = {str(r.get("name")) for r in existing if isinstance(r, dict)}

    desired_roles = ["view-users", "query-users"]
    missing = [rn for rn in desired_roles if rn not in existing_names]
    roles_to_add = [
        _kc_get_role(kc_base, realm=realm, token=token, client_uuid=realm_mgmt_uuid, role_name=rn, verify=verify)
        for rn in missing
    ]
    _kc_add_client_role_mappings(kc_base, realm=realm, token=token, user_id=svc_user_id, client_uuid=realm_mgmt_uuid, roles=roles_to_add, verify=verify)

    secret = _kc_get_client_secret(kc_base, realm=realm, token=token, client_uuid=client_uuid, verify=verify)

    # Verify client_credentials works (fail fast, no secret output)
    _kc_verify_client_credentials(kc_base, realm=realm, client_id=client_id, client_secret=secret, verify=verify)

    # Sync `.env` for the app
    _update_env("KC_ADMIN_REALM", realm)
    _update_env("KC_ADMIN_CLIENT_ID", client_id)
    _update_env("KC_ADMIN_CLIENT_SECRET", secret)

    print("Synced Keycloak admin client into .env (KC_ADMIN_REALM/ID/SECRET). Secret not printed.")


if __name__ == "__main__":
    # Silence requests warnings when verify=False is used (local dev only).
    if os.getenv("PYTHONWARNINGS") is None:
        os.environ["PYTHONWARNINGS"] = "ignore:Unverified HTTPS request"
    main()
