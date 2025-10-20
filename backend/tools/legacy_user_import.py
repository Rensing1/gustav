"""Legacy → Keycloak user migration helper.

Targets the legacy Supabase auth database (`legacy_import`) and recreates the
users in Keycloak while preserving bcrypt password hashes. After the first
login, Keycloak re-hashes the password according to the configured realm policy
(pbkdf2 by default).

Usage example:

    python -m backend.tools.legacy_user_import \
        --legacy-dsn postgresql://postgres:postgres@127.0.0.1:54322/legacy_import \
        --kc-base-url http://127.0.0.1:8100 \
        --kc-host-header id.localhost \
        --kc-admin-user gustav-admin \
        --kc-admin-pass '...'

Environment variables (LEGACY_IMPORT_DSN, KEYCLOAK_BASE_URL, KEYCLOAK_HOST,
KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD) can be used instead of CLI flags.
"""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from typing import Iterable, Sequence
from uuid import UUID

import psycopg
import requests


logger = logging.getLogger("gustav.tools.legacy_import")


try:
    # Prefer absolute import path used by the web layer during tests
    from identity_access.domain import ALLOWED_ROLES
except Exception:  # pragma: no cover - fallback when executed as a package module
    from backend.identity_access.domain import ALLOWED_ROLES  # type: ignore


@dataclass(frozen=True)
class LegacyUserRow:
    """Representation of a legacy Supabase user."""

    id: UUID
    email: str
    role: str
    full_name: str | None
    password_hash: str


def fetch_legacy_users(
    dsn: str,
    emails: Sequence[str] | None = None,
) -> list[LegacyUserRow]:
    """Return legacy users from Supabase/legacy_import.

    Parameters
    ----------
    dsn:
        Psycopg connection string.
    emails:
        Optional list of emails to limit the query. When omitted, all users are
        returned.
    """

    sql_template = """
        SELECT u.id, u.email, p.role, p.full_name, u.encrypted_password
        FROM auth.users u
        JOIN public.profiles p ON p.id = u.id
        {where}
        ORDER BY u.created_at
    """
    where_clause = ""
    params: tuple | None = None
    if emails:
        where_clause = "WHERE u.email = ANY(%s)"
        params = (list(emails),)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Prefer safe composition via psycopg.sql when available. Fallback
            # to a controlled string substitution (only toggles a static WHERE
            # clause, no user-provided identifiers).
            try:  # pragma: no cover - exercised when psycopg.sql is present
                from psycopg import sql as _sql  # type: ignore
                where_sql = _sql.SQL("WHERE u.email = ANY(%s)") if emails else _sql.SQL("")
                stmt = _sql.SQL(sql_template).format(where=where_sql)
                cur.execute(stmt, params)
            except Exception:
                cur.execute(sql_template.format(where=where_clause), params)
            rows = cur.fetchall()

    result = []
    for row in rows:
        user_id, email, role, full_name_raw, password_hash = row
        normalized_name: str | None = None
        if isinstance(full_name_raw, str):
            trimmed = full_name_raw.strip()
            normalized_name = trimmed or None
        elif full_name_raw is not None:
            normalized_name = str(full_name_raw) or None
        result.append(
            LegacyUserRow(
                id=user_id,
                email=email,
                role=role,
                full_name=normalized_name,
                password_hash=password_hash,
            )
        )
    return result


def build_user_payload(row: LegacyUserRow) -> dict:
    """Build the Keycloak user representation for creation.

    Keeps the bcrypt hash and stores the legacy UUID for traceability.
    """

    display_name = row.full_name.strip() if row.full_name else ""
    if not display_name:
        display_name = row.email.split("@", 1)[0]

    return {
        "username": row.email,
        "email": row.email,
        "enabled": True,
        "emailVerified": True,
        "attributes": {
            "display_name": [display_name],
            "legacy_user_id": [str(row.id)],
        },
        "credentials": [
            {
                "type": "password",
                "algorithm": "bcrypt",
                "hashIterations": -1,
                "hashedSaltedValue": row.password_hash,
                "temporary": False,
            }
        ],
    }


class KeycloakAdminClient:
    """Minimal Keycloak admin client (sync, requests-based)."""

    def __init__(
        self,
        base_url: str,
        realm: str,
        token: str,
        host_header: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.realm = realm
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Host": host_header,
        })

    @classmethod
    def from_credentials(
        cls,
        base_url: str,
        host_header: str,
        realm: str,
        username: str,
        password: str,
        *,
        timeout: float = 5.0,
    ) -> "KeycloakAdminClient":
        session = requests.Session()
        session.headers.update({"Host": host_header})
        # Honor optional custom CA bundle for TLS verification; default to verify=True
        ca_bundle = os.getenv("KEYCLOAK_CA_BUNDLE")
        session.verify = ca_bundle if ca_bundle else True
        token_resp = session.post(
            f"{base_url.rstrip('/')}/realms/master/protocol/openid-connect/token",
            data={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            timeout=timeout,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]
        return cls(base_url, realm, token, host_header, session=session, timeout=timeout)

    # --- REST helpers -----------------------------------------------------

    def find_user_id(self, email: str) -> str | None:
        resp = self.session.get(
            f"{self.base_url}/admin/realms/{self.realm}/users",
            params={"email": email, "exact": "true"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return data[0]["id"]

    def delete_user(self, user_id: str) -> None:
        resp = self.session.delete(
            f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}",
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def create_user(self, payload: dict) -> str:
        resp = self.session.post(
            f"{self.base_url}/admin/realms/{self.realm}/users",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        location = resp.headers.get("Location")
        if location:
            return location.rstrip("/").split("/")[-1]
        user_id = self.find_user_id(payload["email"])
        if not user_id:
            raise RuntimeError("User creation succeeded but id lookup failed")
        return user_id

    def assign_realm_role(self, user_id: str, role: str) -> None:
        resp = self.session.get(
            f"{self.base_url}/admin/realms/{self.realm}/roles/{role}",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        role_repr = resp.json()
        resp = self.session.post(
            f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/role-mappings/realm",
            json=[role_repr],
            timeout=self.timeout,
        )
        resp.raise_for_status()


def import_legacy_users(
    rows: Iterable[LegacyUserRow],
    *,
    client: KeycloakAdminClient,
    delete_existing: bool = False,
) -> None:
    """Import users into Keycloak using the provided admin client."""

    for row in rows:
        if row.role not in ALLOWED_ROLES:
            logger.warning("Skip %s – unsupported role %s", row.email, row.role)
            continue

        existing_id = client.find_user_id(row.email) if delete_existing else None
        if existing_id:
            logger.info("Deleting existing user %s (%s)", _mask_email(row.email), existing_id)
            client.delete_user(existing_id)

        payload = build_user_payload(row)
        user_id = client.create_user(payload)
        logger.info("Created user %s -> %s", _mask_email(row.email), user_id)
        client.assign_realm_role(user_id, row.role)


def _validate_host(h: str) -> str:
    """Validate host header format (simple allowlist of characters).

    Accept letters, digits, dashes, dots, and optional :port. Reject whitespace
    or control characters to prevent header injection.
    """
    import re
    if not re.match(r"^[A-Za-z0-9.-]+(?::[0-9]{1,5})?$", (h or "")):
        raise SystemExit("Invalid --kc-host-header (expected hostname[:port])")
    return h


def _mask_email(email: str) -> str:
    """Mask email for logs to reduce PII exposure in admin tool logs."""
    try:
        local, _, domain = email.partition("@")
        return f"{local[:2]}***@{domain}"
    except Exception:
        return "***"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy Supabase users into Keycloak")
    parser.add_argument("--legacy-dsn", default=os.getenv("LEGACY_IMPORT_DSN"))
    parser.add_argument("--kc-base-url", default=os.getenv("KEYCLOAK_BASE_URL", "http://127.0.0.1:8100"))
    parser.add_argument("--kc-host-header", default=os.getenv("KEYCLOAK_HOST", "id.localhost"))
    parser.add_argument("--kc-admin-user", default=os.getenv("KEYCLOAK_ADMIN_USER", "gustav-admin"))
    parser.add_argument("--kc-admin-pass", default=os.getenv("KEYCLOAK_ADMIN_PASSWORD"))
    parser.add_argument("--realm", default=os.getenv("KEYCLOAK_REALM", "gustav"))
    parser.add_argument("--emails", nargs="*", help="Limit import to the given email addresses")
    parser.add_argument("--dry-run", action="store_true", help="Fetch users but do not modify Keycloak")
    parser.add_argument("--force-replace", action="store_true", help="Delete existing users before create")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("KEYCLOAK_TIMEOUT", "5")), help="HTTP timeout in seconds for admin calls")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = _parse_args()

    if not args.legacy_dsn:
        raise SystemExit("--legacy-dsn or LEGACY_IMPORT_DSN must be provided")
    if not args.kc_admin_pass:
        raise SystemExit("--kc-admin-pass or KEYCLOAK_ADMIN_PASSWORD must be provided")

    logger.info("Fetching legacy users…")
    rows = fetch_legacy_users(args.legacy_dsn, emails=args.emails)
    logger.info("Found %d legacy users", len(rows))

    if args.dry_run:
        for row in rows:
            logger.info("[dry-run] Would import %s (%s)", row.email, row.role)
        return

    # Validate host header input for safety
    args.kc_host_header = _validate_host(args.kc_host_header)

    client = KeycloakAdminClient.from_credentials(
        base_url=args.kc_base_url,
        host_header=args.kc_host_header,
        realm=args.realm,
        username=args.kc_admin_user,
        password=args.kc_admin_pass,
        timeout=args.timeout,
    )

    import_legacy_users(rows, client=client, delete_existing=args.force_replace)
    logger.info("Import completed")


if __name__ == "__main__":  # pragma: no cover - manual entry point
    main()
