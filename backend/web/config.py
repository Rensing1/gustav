"""
Configuration and startup security checks for GUSTAV.

Why: In education contexts we must prevent accidental insecure deployments.
This module provides a single guard that enforces minimal production safety
constraints without burdening local development.

Permissions: The caller needs no special privileges. The function simply reads
environment variables and raises `SystemExit` on fatal misconfiguration.
"""
from __future__ import annotations

import os


def _is_prod_like(env: str) -> bool:
    env_l = (env or "").lower()
    return env_l in {"prod", "production", "stage", "staging"}


def ensure_secure_config_on_startup() -> None:
    """Fail fast on insecure production configuration.

    Intent: Abort process startup when obviously insecure settings are detected
    in production/staging. Development remains permissive for convenience.

    Checks:
    - Supabase Service Role key must be set and not a known dummy placeholder.
    - DATABASE_URL must not explicitly disable TLS in prod-like envs.
    - DATABASE_URL user must not be the application role `gustav_limited` in
      prod-like envs (role is NOLOGIN by design; use an env-specific login that
      is IN ROLE gustav_limited).
    """

    env = os.getenv("GUSTAV_ENV", "dev")
    if not _is_prod_like(env):
        return  # dev/test remain permissive

    # 1) Supabase Service Role key
    srole = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not srole or srole.upper() == "DUMMY_DO_NOT_USE":
        raise SystemExit(
            "Refusing to start: SUPABASE_SERVICE_ROLE_KEY is unset or a dummy placeholder in production."
        )

    # 1b) Keycloak admin client secret must be configured (no password grant in prod)
    kc_secret = (os.getenv("KC_ADMIN_CLIENT_SECRET", "") or "").strip()
    if not kc_secret or kc_secret.upper().startswith("CHANGE_ME"):
        raise SystemExit(
            "Refusing to start: KC_ADMIN_CLIENT_SECRET is unset or a placeholder in production."
        )

    # 2) Postgres TLS: basic guard to avoid explicit disable
    dsn = os.getenv("DATABASE_URL", "")
    if "sslmode=disable" in dsn:
        raise SystemExit(
            "Refusing to start: DATABASE_URL contains sslmode=disable in production. Use sslmode=require or verify TLS."
        )

    # 3) DSN user must not be the app role in prod-like envs
    def _parse_user(dsn_value: str) -> str | None:
        try:
            if "://" in dsn_value:
                from urllib.parse import urlparse

                parsed = urlparse(dsn_value)
                return parsed.username
            # Keyword form: host=... user=... dbname=...
            import re

            m = re.search(r"\buser\s*=\s*([^\s]+)", dsn_value)
            return m.group(1) if m else None
        except Exception:
            return None

    for key in ("DATABASE_URL", "TEACHING_DATABASE_URL", "SESSION_DATABASE_URL"):
        val = os.getenv(key, "")
        if not val:
            continue
        user = (_parse_user(val) or "").lower()
        if user == "gustav_limited":
            raise SystemExit(
                f"Refusing to start: {key} authenticates as 'gustav_limited' in production. "
                "Create an environment-specific login role that is IN ROLE gustav_limited and use that instead."
            )
