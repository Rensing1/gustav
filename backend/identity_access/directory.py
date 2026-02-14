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

from typing import Callable, Dict, List
import re
import os
import logging
import requests
from identity_access.domain import ALLOWED_ROLES

logger = logging.getLogger(__name__)


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
        # Accept both KC_ADMIN_PASSWORD and KC_ADMIN_PASS (Makefile uses KC_ADMIN_PASS)
        self.admin_password = os.getenv("KC_ADMIN_PASSWORD") or os.getenv("KC_ADMIN_PASS")

    @staticmethod
    def _verify_opt():
        # Honor CA bundle in production environments; default to system CAs
        ca = os.getenv("KEYCLOAK_CA_BUNDLE")
        return ca if ca else True

    def _token_client_credentials(
        self,
        *,
        realm: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> str:
        secret = client_secret or self.admin_client_secret
        if not secret:
            raise RuntimeError("missing_client_secret")
        rid = str(realm or self.admin_realm)
        cid = str(client_id or self.admin_client_id)
        url = f"{self.base_url}/realms/{rid}/protocol/openid-connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
        }
        r = requests.post(url, data=data, timeout=10, verify=self._verify_opt(), allow_redirects=False)
        r.raise_for_status()
        tok = (r.json() or {}).get("access_token")
        if not tok:
            raise RuntimeError("keycloak_admin_token_missing")
        return str(tok)

    def _token_password_grant(self, *, realm: str, client_id: str, allow_in_prod: bool) -> str:
        env = (os.getenv("GUSTAV_ENV", "dev") or "").lower()
        if not allow_in_prod and env in {"prod", "production", "stage", "staging"}:
            raise RuntimeError("password_grant_disabled_in_prod")
        if not self.admin_username or not self.admin_password:
            raise RuntimeError("missing_admin_username_password")
        url = f"{self.base_url}/realms/{realm}/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": client_id,
            "username": self.admin_username,
            "password": self.admin_password,
        }
        r = requests.post(url, data=data, timeout=10, verify=self._verify_opt(), allow_redirects=False)
        r.raise_for_status()
        tok = (r.json() or {}).get("access_token")
        if not tok:
            raise RuntimeError("keycloak_admin_token_missing")
        return str(tok)

    def token(self) -> str:
        """Obtain the primary admin bearer token."""
        if self.admin_client_secret:
            return self._token_client_credentials()
        return self._token_password_grant(
            realm=self.admin_realm,
            client_id=self.admin_client_id,
            allow_in_prod=False,
        )

    def token_admin_fallback(self) -> str | None:
        """Best-effort fallback token via dedicated fallback confidential client.

        Why:
            Some deployments grant enough rights for `/users` but not for
            `/roles/{role}/users` to the configured confidential client. This
            retry path keeps role-based search/list deterministic without a
            broad users scan.
        """
        client_id = os.getenv("KC_ADMIN_FALLBACK_CLIENT_ID", "admin-cli")
        client_secret = os.getenv("KC_ADMIN_FALLBACK_CLIENT_SECRET")
        realm = os.getenv("KC_ADMIN_FALLBACK_REALM", "master")
        if not client_secret:
            return None
        try:
            return self._token_client_credentials(
                realm=realm,
                client_id=client_id,
                client_secret=client_secret,
            )
        except Exception as exc:
            logger.warning("Directory fallback token acquisition failed: %s", exc.__class__.__name__)
            return None

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


def localpart_identifier(s: str) -> str:
    """Return localpart from email/legacy-email-like identifier."""
    if not s:
        return ""
    value = str(s).strip()
    if value.startswith("legacy-email:"):
        value = value.split(":", 1)[1]
    if "@" in value:
        return value.split("@", 1)[0].strip()
    return ""


def _localpart_identifier(s: str) -> str:
    """Backward-compatible wrapper around localpart extraction helper."""
    return localpart_identifier(s)


def _login_label(u: dict) -> str:
    """Return login-like user label for members UI (prefer email localpart)."""
    email = (u.get("email") or "").strip()
    if email:
        lp = localpart_identifier(email)
        if lp:
            return lp
    uname = (u.get("username") or "").strip()
    if uname:
        lp = localpart_identifier(uname)
        if lp:
            return lp
    return _display_name(u)


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


def _role_sources(*, role: str, realm: str) -> List[str]:
    """Return Keycloak role source names for a requested app role.

    Why:
        Some realms grant `student` effectively via the composite
        `default-roles-{realm}`. We include both sources for student lookup so
        freshly registered users appear without manual role patching.
    """
    if role == "student":
        return [role, f"default-roles-{realm}"]
    return [role]


def _int_env_clamped(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = str(os.getenv(name, str(default)) or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(min_value, min(max_value, value))


def _fetch_role_users_page(
    *,
    kc: _KC,
    token: str,
    role_name: str,
    first: int,
    max_items: int,
    verify_opt,
    allow_missing_role: bool = False,
) -> List[dict]:
    """Fetch one page of users for a Keycloak realm role."""
    url = f"{kc.base_url}/admin/realms/{kc.realm}/roles/{role_name}/users"
    params = {"first": first, "max": max_items}
    r = requests.get(
        url,
        headers=kc.hdr(token),
        params=params,
        timeout=10,
        verify=verify_opt,
        allow_redirects=False,
    )
    if allow_missing_role and r.status_code == 404:
        return []
    if r.status_code == 403:
        raise PermissionError("role_users_forbidden")
    r.raise_for_status()
    arr = r.json() or []
    return arr if isinstance(arr, list) else []


def _execute_with_role_users_retry(
    *,
    kc: _KC,
    operation: Callable[[str], List[dict]],
) -> List[dict]:
    """Run role-users operation and retry once with fallback admin token on 403."""
    try:
        return operation(kc.token())
    except PermissionError:
        logger.warning("Directory role-users request forbidden for primary admin token; trying fallback token")
        retry_token = kc.token_admin_fallback()
        if not retry_token:
            logger.warning("Directory fallback token unavailable; returning empty role-users result")
            return []
        try:
            return operation(retry_token)
        except PermissionError:
            logger.warning("Directory role-users request forbidden for fallback token; returning empty result")
            return []


def _execute_with_role_users_retry_map(
    *,
    kc: _KC,
    operation: Callable[[str], Dict[str, str]],
) -> Dict[str, str]:
    """Run role-users map operation and retry once with fallback admin token on 403."""
    try:
        return operation(kc.token())
    except PermissionError:
        logger.warning("Directory role-users map request forbidden for primary token; trying fallback token")
        retry_token = kc.token_admin_fallback()
        if not retry_token:
            logger.warning("Directory fallback token unavailable; returning empty role-users map")
            return {}
        try:
            return operation(retry_token)
        except PermissionError:
            logger.warning("Directory role-users map request forbidden for fallback token; returning empty result")
            return {}


def search_users_by_name(*, role: str, q: str, limit: int) -> List[dict]:
    """Search users by role and display name fragment (pages through role members).

    Why:
        Keycloak's role users endpoint is paginated. Filtering only the first
        page can miss matches outside that window. We iterate over pages until
        we collect `limit` matches or exhaust available pages, capping the scan
        to a reasonable upper bound.

    Returns: list of { sub, name } where `sub` is the Keycloak user ID.
    """
    kc = _KC()
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid role")
    role_names = _role_sources(role=role, realm=kc.realm)
    verify_opt = kc._verify_opt()
    ql = (q or "").strip().lower()

    def _search_with_token(current_token: str) -> List[dict]:
        results: List[dict] = []
        seen_subs: set[str] = set()
        # Page across role members; KC caps max to ~200; we use batch=200
        batch = 200
        scanned_total = 0
        scan_cap = 2000  # do not scan unboundedly
        for idx, role_name in enumerate(role_names):
            first = 0
            while len(results) < max(1, int(limit)) and scanned_total < scan_cap:
                arr = _fetch_role_users_page(
                    kc=kc,
                    token=current_token,
                    role_name=role_name,
                    first=first,
                    max_items=batch,
                    verify_opt=verify_opt,
                    allow_missing_role=(idx > 0),
                )
                if not arr:
                    break
                scanned_total += len(arr)
                for u in arr:
                    sub = str(u.get("id") or "")
                    if not sub or sub in seen_subs:
                        continue
                    seen_subs.add(sub)
                    name = _display_name(u)
                    uname = str(u.get("username", ""))
                    if ql in name.lower() or (ql and ql in uname.lower()):
                        results.append({"sub": sub, "name": name})
                        if len(results) >= limit:
                            break
                # Advance to next page
                first += batch
                if len(arr) < batch:  # last page
                    break
        return results

    return _execute_with_role_users_retry(kc=kc, operation=_search_with_token)


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
            r = requests.get(url, headers=kc.hdr(token), timeout=10, verify=verify_opt, allow_redirects=False)
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
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid role")
    role_names = _role_sources(role=role, realm=kc.realm)
    want_offset = max(0, int(offset or 0))
    want_limit = max(1, min(200, int(limit or 50)))
    verify_opt = kc._verify_opt()
    def _list_with_token(current_token: str) -> List[dict]:
        # Keep direct KC pagination for non-student roles (no behavior change).
        if len(role_names) == 1:
            arr = _fetch_role_users_page(
                kc=kc,
                token=current_token,
                role_name=role,
                first=want_offset,
                max_items=want_limit,
                verify_opt=verify_opt,
            )
            results: List[dict] = []
            for u in arr:
                name = _display_name(u)
                sub = u.get("id")
                if sub and name:
                    results.append({"sub": str(sub), "name": name})
            return results

        # Student: merge direct role and default-role members; dedupe by subject.
        target = want_offset + want_limit
        batch = 200
        merged: List[dict] = []
        seen_subs: set[str] = set()
        for idx, role_name in enumerate(role_names):
            first = 0
            while len(merged) < target:
                arr = _fetch_role_users_page(
                    kc=kc,
                    token=current_token,
                    role_name=role_name,
                    first=first,
                    max_items=batch,
                    verify_opt=verify_opt,
                    allow_missing_role=(idx > 0),
                )
                if not arr:
                    break
                for u in arr:
                    sub = str(u.get("id") or "")
                    if not sub or sub in seen_subs:
                        continue
                    seen_subs.add(sub)
                    merged.append(u)
                    if len(merged) >= target:
                        break
                first += batch
                if len(arr) < batch:
                    break

        results: List[dict] = []
        for u in merged[want_offset : want_offset + want_limit]:
            name = _display_name(u)
            sub = u.get("id")
            if sub and name:
                results.append({"sub": str(sub), "name": name})
        return results
    return _execute_with_role_users_retry(kc=kc, operation=_list_with_token)


def resolve_student_login_labels(subs: List[str]) -> Dict[str, str]:
    """Resolve student ids to login-style labels (email localpart).

    Returns mapping for provided `subs`; missing users are mapped to
    "Unbekannt". This is used by the members SSR UI where teachers want
    identifiers consistent with classroom logins.
    """
    kc = _KC()
    verify_opt = kc._verify_opt()
    unique_subs = list(dict.fromkeys(str(sid or "").strip() for sid in subs if str(sid or "").strip()))
    if not unique_subs:
        return {}
    max_requested_subs = _int_env_clamped("DIRECTORY_LOGIN_LABEL_MAX_SUBS", 200, 1, 1000)
    requested_subs = unique_subs[:max_requested_subs]
    unresolved = set(requested_subs)
    role_names = _role_sources(role="student", realm=kc.realm)
    batch = _int_env_clamped("DIRECTORY_LOGIN_LABEL_BATCH_SIZE", 200, 50, 200)
    scan_cap = _int_env_clamped("DIRECTORY_LOGIN_LABEL_SCAN_CAP", 4000, 200, 20000)

    def _resolve_with_token(current_token: str) -> Dict[str, str]:
        found: Dict[str, str] = {}
        remaining = set(unresolved)
        scanned_total = 0
        for idx, role_name in enumerate(role_names):
            first = 0
            while remaining and scanned_total < scan_cap:
                arr = _fetch_role_users_page(
                    kc=kc,
                    token=current_token,
                    role_name=role_name,
                    first=first,
                    max_items=batch,
                    verify_opt=verify_opt,
                    allow_missing_role=(idx > 0),
                )
                if not arr:
                    break
                scanned_total += len(arr)
                for u in arr:
                    sub = str(u.get("id") or "")
                    if not sub or sub not in remaining:
                        continue
                    label = _login_label(u)
                    found[sub] = label if label else "Unbekannt"
                    remaining.discard(sub)
                    if not remaining:
                        break
                first += batch
                if len(arr) < batch:
                    break
        return found

    found = _execute_with_role_users_retry_map(kc=kc, operation=_resolve_with_token)
    out: Dict[str, str] = {}
    for sid in unique_subs:
        if sid in found:
            out[sid] = found[sid]
        else:
            out[sid] = "Unbekannt"
    return out
