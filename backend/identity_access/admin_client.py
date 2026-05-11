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
import logging
import requests

from .directory import _KC
from .oidc import OIDCConfig


logger = logging.getLogger(__name__)


class AdminClient:
    def __init__(self, cfg: OIDCConfig) -> None:
        self.cfg = cfg
        self._kc = _KC()
        self._kc.base_url = str(cfg.base_url).rstrip("/")
        self._kc.realm = str(cfg.realm)

    def _token(self) -> str:
        return self._kc.token()

    def _admin(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def get_user(self, *, user_id: str) -> Dict[str, object]:
        """Load one Keycloak user by subject/id."""
        token = self._token()
        url = f"{self.cfg.base_url}/admin/realms/{self.cfg.realm}/users/{user_id}"
        response = requests.get(
            url,
            headers=self._admin(token),
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        if response.status_code == 404:
            raise ValueError("user_not_found")
        response.raise_for_status()
        payload = response.json() or {}
        return payload if isinstance(payload, dict) else {}

    def update_user(self, *, user_id: str, payload: Dict[str, object]) -> None:
        """Update one Keycloak user with a minimal partial payload.

        Why:
            Profile edits may run against externally managed accounts where
            login fields such as `username` or `email` are read-only. Callers
            should therefore send only the fields that belong to the concrete
            use case.
        """
        token = self._token()
        url = f"{self.cfg.base_url}/admin/realms/{self.cfg.realm}/users/{user_id}"
        response = requests.put(
            url,
            headers=self._admin(token),
            json=payload,
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        if response.status_code not in (204,):
            logger.warning(
                "Keycloak user update failed for user_id=%s status=%s error=user_update_failed",
                user_id,
                response.status_code,
            )
            raise ValueError("user_update_failed")

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
        r = requests.post(
            url,
            headers=self._admin(token),
            json=payload,
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        if r.status_code not in (201, 204):
            raise ValueError("user_create_failed")
        # Get created user id by querying by exact email (simplest approach)
        q = requests.get(
            url,
            headers=self._admin(token),
            params={"email": email, "exact": True},
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
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
        pr = requests.put(
            pw_url,
            headers=self._admin(token),
            json=pw,
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        if pr.status_code not in (204,):
            raise ValueError("password_set_failed")
        return str(user_id)

    def assign_realm_role(self, *, user_id: str, role_name: str) -> None:
        token = self._token()
        base = f"{self.cfg.base_url}/admin/realms/{self.cfg.realm}"
        role = requests.get(
            f"{base}/roles/{role_name}",
            headers=self._admin(token),
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        role.raise_for_status()
        role_json = role.json()
        if not role_json or "id" not in role_json:
            raise ValueError("role_not_found")
        mapping_url = f"{base}/users/{user_id}/role-mappings/realm"
        add = requests.post(
            mapping_url,
            headers=self._admin(token),
            json=[role_json],
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        if add.status_code not in (204,):
            raise ValueError("role_assign_failed")

    def get_realm_roles(self, *, user_id: str) -> list[str]:
        """Return current realm role names for one Keycloak user."""
        token = self._token()
        url = f"{self.cfg.base_url}/admin/realms/{self.cfg.realm}/users/{user_id}/role-mappings/realm"
        response = requests.get(
            url,
            headers=self._admin(token),
            timeout=10,
            verify=self._kc._verify_opt(),
            allow_redirects=False,
        )
        if response.status_code == 404:
            raise ValueError("user_not_found")
        response.raise_for_status()
        payload = response.json() or []
        if not isinstance(payload, list):
            return []
        roles: list[str] = []
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                roles.append(str(item["name"]))
        return roles
