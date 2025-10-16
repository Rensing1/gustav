"""
Keycloak Admin client (minimal) for user provisioning and role assignment.

Design:
- Framework-agnostic, callable from web adapters.
- Uses requests under the hood; callers are responsible for exception handling.

Security:
- Do not log credentials or tokens.
- Expect credentials (client-secret or admin user) from environment in prod.
"""

from __future__ import annotations

from typing import Dict
import os
import requests

from .oidc import OIDCConfig


class AdminClient:
    def __init__(self, cfg: OIDCConfig) -> None:
        self.cfg = cfg
        self._admin_realm = os.getenv("KC_ADMIN_REALM", "master")
        self._admin_client_id = os.getenv("KC_ADMIN_CLIENT_ID", "admin-cli")
        self._admin_username = os.getenv("KC_ADMIN_USERNAME")
        self._admin_password = os.getenv("KC_ADMIN_PASSWORD")

    def _token(self) -> str:
        url = f"{self.cfg.base_url}/realms/{self._admin_realm}/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": self._admin_client_id,
            "username": self._admin_username,
            "password": self._admin_password,
        }
        r = requests.post(url, data=data, timeout=10)
        r.raise_for_status()
        return r.json().get("access_token", "")

    def _admin(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def create_user(self, *, email: str, password: str, display_name: str | None = None) -> str:
        token = self._token()
        url = f"{self.cfg.base_url}/admin/realms/{self.cfg.realm}/users"
        payload = {
            "username": email,
            "email": email,
            "enabled": True,
            "emailVerified": False,
            **({"firstName": display_name} if display_name else {}),
        }
        r = requests.post(url, headers=self._admin(token), json=payload, timeout=10)
        if r.status_code not in (201, 204):
            raise ValueError("user_create_failed")
        # Get created user id by querying by exact email (simplest approach)
        q = requests.get(
            url, headers=self._admin(token), params={"email": email, "exact": True}, timeout=10
        )
        q.raise_for_status()
        arr = q.json() or []
        if not arr:
            raise ValueError("user_lookup_failed")
        user_id = arr[0].get("id")
        if not user_id:
            raise ValueError("user_id_missing")
        # Set password (reset-credential endpoint)
        pw_url = f"{url}/{user_id}/reset-password"
        pw = {"type": "password", "value": password, "temporary": False}
        pr = requests.put(pw_url, headers=self._admin(token), json=pw, timeout=10)
        if pr.status_code not in (204,):
            raise ValueError("password_set_failed")
        return str(user_id)

    def assign_realm_role(self, *, user_id: str, role_name: str) -> None:
        token = self._token()
        base = f"{self.cfg.base_url}/admin/realms/{self.cfg.realm}"
        role = requests.get(f"{base}/roles/{role_name}", headers=self._admin(token), timeout=10)
        role.raise_for_status()
        role_json = role.json()
        if not role_json or "id" not in role_json:
            raise ValueError("role_not_found")
        mapping_url = f"{base}/users/{user_id}/role-mappings/realm"
        add = requests.post(mapping_url, headers=self._admin(token), json=[role_json], timeout=10)
        if add.status_code not in (204,):
            raise ValueError("role_assign_failed")

