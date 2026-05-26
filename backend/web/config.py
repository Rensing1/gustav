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

    # 1c) Internal BFF shared secret must be configured for the frontend-backend bridge.
    bff_secret = (os.getenv("BFF_INTERNAL_SHARED_SECRET", "") or "").strip()
    if not bff_secret or bff_secret.upper().startswith("CHANGE_ME"):
        raise SystemExit(
            "Refusing to start: BFF_INTERNAL_SHARED_SECRET is unset or a placeholder in production."
        )

    # 1d) H5P teacher review capability token secret must be configured.
    # Used to sign short-lived review tokens consumed by the H5P sidecar.
    h5p_review_secret = (os.getenv("H5P_REVIEW_TOKEN_SECRET", "") or "").strip()
    if not h5p_review_secret or h5p_review_secret.upper().startswith("CHANGE_ME"):
        raise SystemExit(
            "Refusing to start: H5P_REVIEW_TOKEN_SECRET is unset or a placeholder in production."
        )

    # 1e) Internal Web-to-H5P shared secret must be configured for CLI package workflows.
    h5p_internal_secret = (os.getenv("H5P_INTERNAL_SHARED_SECRET", "") or "").strip()
    if not h5p_internal_secret or h5p_internal_secret.upper().startswith("CHANGE_ME"):
        raise SystemExit(
            "Refusing to start: H5P_INTERNAL_SHARED_SECRET is unset or a placeholder in production."
        )

    # 1f) SSR/browser CSRF token secret must be independent from H5P secrets.
    # Keep secrets separated so rotation/leak blast radius stays minimal.
    csrf_secret = (os.getenv("APP_CSRF_TOKEN_SECRET", "") or "").strip()
    if (
        not csrf_secret
        or csrf_secret.upper().startswith("CHANGE_ME")
        or csrf_secret.upper() == "DUMMY_DO_NOT_USE"
    ):
        raise SystemExit(
            "Refusing to start: APP_CSRF_TOKEN_SECRET is unset or a placeholder in production."
        )

    # 2) Postgres TLS: forbid explicit disable in all configured DSNs
    for key in ("DATABASE_URL", "TEACHING_DATABASE_URL", "LEARNING_DATABASE_URL", "SESSION_DATABASE_URL"):
        dsn = os.getenv(key, "") or ""
        if "sslmode=disable" in dsn:
            raise SystemExit(
                f"Refusing to start: {key} contains sslmode=disable in production. "
                "Use sslmode=require or verify TLS."
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

    for key in ("DATABASE_URL", "TEACHING_DATABASE_URL", "LEARNING_DATABASE_URL", "SESSION_DATABASE_URL"):
        val = os.getenv(key, "")
        if not val:
            continue
        user = (_parse_user(val) or "").lower()
        if user == "gustav_limited":
            raise SystemExit(
                f"Refusing to start: {key} authenticates as 'gustav_limited' in production. "
                "Create an environment-specific login role that is IN ROLE gustav_limited and use that instead."
            )

    # 4) Keycloak endpoints:
    #    - KC_PUBLIC_BASE_URL is browser-facing and must use HTTPS in prod-like envs.
    #    - KC_BASE_URL is server-to-server. In our docker-compose deployments,
    #      this commonly targets the internal service hostname (e.g. http://keycloak:8080).
    #      Allow plain HTTP only for clearly internal hostnames to avoid the
    #      common *.localhost-inside-container footgun and to keep E2E (prod-like)
    #      runnable in local compose.
    def _must_be_https_or_internal_http(url_value: str, var_name: str) -> None:
        try:
            if not url_value:
                return
            raw = url_value.strip()
            val = raw.lower()
            if val.startswith("https://"):
                return
            if not val.startswith("http://"):
                raise SystemExit(f"Refusing to start: invalid {var_name} value in production.")
            from urllib.parse import urlparse

            host = (urlparse(raw).hostname or "").lower()
            allowed_internal = {"keycloak", "gustav-keycloak", "localhost", "127.0.0.1", "::1"}
            if host not in allowed_internal:
                raise SystemExit(
                    f"Refusing to start: {var_name} must use https in production unless it targets an internal hostname."
                )
        except SystemExit:
            raise
        except Exception:
            # If parsing fails, be conservative and abort
            raise SystemExit(f"Refusing to start: invalid {var_name} value in production.")

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
            raise SystemExit(f"Refusing to start: invalid {var_name} value in production.")

    _must_be_https_or_internal_http(os.getenv("KC_BASE_URL", ""), "KC_BASE_URL")
    _must_be_https(os.getenv("KC_PUBLIC_BASE_URL", ""), "KC_PUBLIC_BASE_URL")

    # 5) Storage verification must be enforced in prod-like envs
    require_verify = (os.getenv("REQUIRE_STORAGE_VERIFY", "false") or "").strip().lower() == "true"
    if not require_verify:
        raise SystemExit(
            "Refusing to start: REQUIRE_STORAGE_VERIFY=true is mandatory in production/staging."
        )

    # 6) Forbid dev upload stub and upload proxy in prod-like envs
    if (os.getenv("ENABLE_DEV_UPLOAD_STUB", "false") or "").strip().lower() == "true":
        raise SystemExit(
            "Refusing to start: ENABLE_DEV_UPLOAD_STUB must be false in production/staging."
        )
    if (os.getenv("ENABLE_STORAGE_UPLOAD_PROXY", "false") or "").strip().lower() == "true":
        raise SystemExit(
            "Refusing to start: ENABLE_STORAGE_UPLOAD_PROXY must be false in production/staging."
        )

    # 7) Forbid automatic bucket provisioning in prod-like envs
    #    Buckets must be provisioned via migrations or explicit runbooks.
    if (os.getenv("AUTO_CREATE_STORAGE_BUCKETS", "false") or "").strip().lower() == "true":
        raise SystemExit(
            "Refusing to start: AUTO_CREATE_STORAGE_BUCKETS=true is not allowed in production/staging. "
            "Provision storage buckets via migrations/runbooks."
        )
