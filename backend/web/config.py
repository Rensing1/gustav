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

    # 4) Keycloak endpoints must use HTTPS in production-like environments
    def _must_be_https(url_value: str, var_name: str) -> None:
        try:
            if not url_value:
                return
            val = url_value.strip().lower()
            if val.startswith("http://"):
                raise SystemExit(
                    f"Refusing to start: {var_name} must use https in production (got http)."
                )
        except SystemExit:
            raise
        except Exception:
            # If parsing fails, be conservative and abort
            raise SystemExit(f"Refusing to start: invalid {var_name} value in production.")

    _must_be_https(os.getenv("KC_BASE_URL", ""), "KC_BASE_URL")
    _must_be_https(os.getenv("KC_PUBLIC_BASE_URL", ""), "KC_PUBLIC_BASE_URL")

    # 5) AI backend safety: stub adapters must never run in prod/stage.
    ai_backend = (os.getenv("AI_BACKEND") or "stub").strip().lower()
    if ai_backend == "stub":
        raise SystemExit(
            "Refusing to start: AI_BACKEND=stub is not allowed in production/staging. Configure a real adapter."
        )

    # 6) Storage verification must be enforced in prod-like envs
    require_verify = (os.getenv("REQUIRE_STORAGE_VERIFY", "false") or "").strip().lower() == "true"
    if not require_verify:
        raise SystemExit(
            "Refusing to start: REQUIRE_STORAGE_VERIFY=true is mandatory in production/staging."
        )

    # 7) Forbid dev upload stub and upload proxy in prod-like envs
    if (os.getenv("ENABLE_DEV_UPLOAD_STUB", "false") or "").strip().lower() == "true":
        raise SystemExit(
            "Refusing to start: ENABLE_DEV_UPLOAD_STUB must be false in production/staging."
        )
    if (os.getenv("ENABLE_STORAGE_UPLOAD_PROXY", "false") or "").strip().lower() == "true":
        raise SystemExit(
            "Refusing to start: ENABLE_STORAGE_UPLOAD_PROXY must be false in production/staging."
        )
