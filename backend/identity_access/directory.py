"""
Directory adapter for user lookup (Keycloak Admin API).

Why:
    Teaching requires searching students by display name and resolving stable
    user IDs (OIDC `sub`) to names for member listings. This adapter wraps the
    minimal Keycloak Admin API calls behind simple functions that return DTOs
    without PII beyond the display name.

Security:
    - Uses admin credentials from environment to obtain a bearer token.
    - Do not log credentials or tokens.
    - Intended for server-side use only.
"""
from __future__ import annotations

from typing import List, Dict
import re
import os
import requests
from identity_access.domain import ALLOWED_ROLES


class _KC:
    def __init__(self) -> None:
        self.base_url = os.getenv("KC_BASE_URL", "http://localhost:8080").rstrip("/")
        self.realm = os.getenv("KC_REALM", "gustav")
        # Token realm for admin client — typically 'master'
        self.admin_realm = os.getenv("KC_ADMIN_REALM", "master")
        # Confidential client for admin API access (preferred)
        self.admin_client_id = os.getenv("KC_ADMIN_CLIENT_ID", "gustav-admin-cli")
        self.admin_client_secret = os.getenv("KC_ADMIN_CLIENT_SECRET")
        # Legacy fallback (password grant) — discouraged; retained for dev only
        self.admin_username = os.getenv("KC_ADMIN_USERNAME")
        self.admin_password = os.getenv("KC_ADMIN_PASSWORD")

    def token(self) -> str:
        """Obtain an admin bearer token.

        Prefers OAuth2 client_credentials using a confidential client. Falls
        back to the legacy password grant only when username/password are set
        and no client secret is configured. Do not enable password grant in
        production.
        """
        url = f"{self.base_url}/realms/{self.admin_realm}/protocol/openid-connect/token"
        # Prefer client credentials
        if self.admin_client_secret:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.admin_client_id,
                "client_secret": self.admin_client_secret,
            }
        else:
            # Forbid password grant in production-like environments
            env = (os.getenv("GUSTAV_ENV", "dev") or "").lower()
            if env in {"prod", "production", "stage", "staging"}:
                raise RuntimeError("password_grant_disabled_in_prod")
            if not self.admin_username or not self.admin_password:
                raise RuntimeError(
                    "Keycloak admin credentials missing: set KC_ADMIN_CLIENT_SECRET or KC_ADMIN_USERNAME/PASSWORD"
                )
            data = {
                "grant_type": "password",
                "client_id": self.admin_client_id,
                "username": self.admin_username,
                "password": self.admin_password,
            }
        # Honor CA bundle in production environments; default to system CAs
        ca = os.getenv("KEYCLOAK_CA_BUNDLE")
        verify_opt = ca if ca else True
        r = requests.post(url, data=data, timeout=10, verify=verify_opt)
        r.raise_for_status()
        tok = (r.json() or {}).get("access_token")
        if not tok:
            raise RuntimeError("Keycloak admin token missing")
        return str(tok)

    def hdr(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_attr(u: dict, key: str) -> str:
    """Fetch a single-valued Keycloak user attribute from `attributes`.

    Keycloak exposes attributes as { key: [values...] }. We return the first string.
    """
    try:
        attrs = u.get("attributes") or {}
        vals = attrs.get(key)
        if isinstance(vals, list) and vals:
            return str(vals[0] or "").strip()
    except Exception:
        pass
    return ""


_splitter = re.compile(r"[^A-Za-z0-9]+")


def humanize_identifier(s: str) -> str:
    """Turn an email/username into a human display name.

    Rules:
    - Strip known prefixes like "legacy-email:".
    - For emails, use the part before '@'.
    - Split on non-alphanumeric separators (._- etc.).
    - Title-case each token and join with a single space.
    - Return single word title-cased if nothing to split.
    """
    if not s:
        return ""
    s = str(s)
    if s.startswith("legacy-email:"):
        s = s.split(":", 1)[1]
    if "@" in s:
        s = s.split("@", 1)[0]
    parts = [p for p in _splitter.split(s) if p]
    if not parts:
        return ""
    return " ".join(p[:1].upper() + p[1:].lower() for p in parts)


def _display_name(u: dict) -> str:
    # 1) explicit display_name attribute
    dn = _get_attr(u, "display_name")
    if dn:
        return dn
    # 2) first + last names
    first = (u.get("firstName") or "").strip()
    last = (u.get("lastName") or "").strip()
    if first or last:
        return " ".join([p for p in (first, last) if p]).strip()
    # 3) email or username humanized
    email = (u.get("email") or "").strip()
    if email:
        h = humanize_identifier(email)
        if h:
            return h
    uname = (u.get("username") or "").strip()
    if uname:
        h = humanize_identifier(uname)
        if h:
            return h
    # 4) final fallback
    return "Unbekannt"


def search_users_by_name(*, role: str, q: str, limit: int) -> List[dict]:
    """Search users by role and display name fragment.

    Returns: list of { sub, name } where `sub` is the Keycloak user ID.
    """
    kc = _KC()
    token = kc.token()
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid role")
    # Role-based listing (avoids mapping calls per user)
    url = f"{kc.base_url}/admin/realms/{kc.realm}/roles/{role}/users"
    params = {"first": 0, "max": max(1, min(200, int(limit) * 2))}
    ca = os.getenv("KEYCLOAK_CA_BUNDLE")
    verify_opt = ca if ca else True
    r = requests.get(url, headers=kc.hdr(token), params=params, timeout=10, verify=verify_opt)
    r.raise_for_status()
    arr = r.json() or []
    ql = (q or "").lower()
    results: List[dict] = []
    for u in arr:
        name = _display_name(u)
        if ql in name.lower() or ql in str(u.get("username", "")).lower():
            sub = u.get("id")
            if sub and name:
                results.append({"sub": str(sub), "name": name})
        if len(results) >= limit:
            break
    return results


def resolve_student_names(subs: List[str]) -> Dict[str, str]:
    """Resolve user IDs to display names using KC Admin API.

    Returns a mapping for the provided subs; unknown ids map to the id itself.
    """
    kc = _KC()
    token = kc.token()
    out: Dict[str, str] = {}
    ca = os.getenv("KEYCLOAK_CA_BUNDLE")
    verify_opt = ca if ca else True
    for sid in subs:
        try:
            url = f"{kc.base_url}/admin/realms/{kc.realm}/users/{sid}"
            r = requests.get(url, headers=kc.hdr(token), timeout=10, verify=verify_opt)
            if r.status_code == 404:
                out[sid] = sid
                continue
            r.raise_for_status()
            u = r.json() or {}
            out[sid] = _display_name(u) or sid
        except Exception:
            out[sid] = sid
    return out


def list_users_by_role(*, role: str, limit: int, offset: int) -> List[dict]:
    """List users for a given role using Keycloak Admin API.

    Returns: list of { sub, name } with pagination.
    """
    kc = _KC()
    token = kc.token()
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid role")
    url = f"{kc.base_url}/admin/realms/{kc.realm}/roles/{role}/users"
    # Use KC pagination directly
    params = {"first": max(0, int(offset or 0)), "max": max(1, min(200, int(limit or 50)))}
    ca = os.getenv("KEYCLOAK_CA_BUNDLE")
    verify_opt = ca if ca else True
    r = requests.get(url, headers=kc.hdr(token), params=params, timeout=10, verify=verify_opt)
    r.raise_for_status()
    arr = r.json() or []
    results: List[dict] = []
    for u in arr:
        name = _display_name(u)
        sub = u.get("id")
        if sub and name:
            results.append({"sub": str(sub), "name": name})
    return results
