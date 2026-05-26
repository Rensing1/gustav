"""
Security config guard tests (TDD first).

Validates that production/staging environments fail fast when the Supabase
Service Role key is unset or a dummy placeholder, while development allows
running with a dummy key for local convenience.
"""
from __future__ import annotations

import importlib

import pytest


def _set_minimal_prod_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a minimal valid production-like env baseline for config guard tests."""

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_NON_DUMMY")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "real-internal-h5p-secret")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )


@pytest.mark.anyio
async def test_service_role_key_guard_prod_raises(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a dummy/unset service role key must abort startup."""
    # Arrange: ensure env looks like production
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DUMMY_DO_NOT_USE")

    # Act/Assert
    # Import the config module and call the guard; it must raise SystemExit
    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_service_role_key_guard_dev_allows_dummy(monkeypatch: pytest.MonkeyPatch):
    """Legacy behavior: In dev env, dummy key tolerated (until dev=prod flip)."""
    # Arrange: dev defaults
    monkeypatch.setenv("GUSTAV_ENV", "dev")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DUMMY_DO_NOT_USE")

    # Act/Assert: should not raise for now (will flip when dev=prod guard is enabled)
    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_dsn_user_guard_prod_raises_if_limited_user(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, DSN must not authenticate as the app role."""
    monkeypatch.setenv("GUSTAV_ENV", "production")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_NON_DUMMY")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "real-internal-h5p-secret")
    # Ensure Keycloak URLs are https to satisfy production guards
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    # Valid TLS setting
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_limited:secret@db.example.com:5432/postgres?sslmode=require",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_dsn_user_guard_prod_allows_nonlimited_user(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a separate login IN ROLE gustav_limited is allowed."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_NON_DUMMY")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "real-internal-h5p-secret")
    # Ensure Keycloak URLs are https to satisfy production guards
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    # Should not raise
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "dsn_var",
    [
        "TEACHING_DATABASE_URL",
        "LEARNING_DATABASE_URL",
        "SESSION_DATABASE_URL",
    ],
)
async def test_prod_rejects_sslmode_disable_in_all_dsns(
    monkeypatch: pytest.MonkeyPatch, dsn_var: str
) -> None:
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.setenv(
        dsn_var,
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=disable",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_dsn_user_guard_prod_rejects_learning_dsn_limited_user(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.setenv(
        "LEARNING_DATABASE_URL",
        "postgresql://gustav_limited:secret@db.example.com:5432/postgres?sslmode=require",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_kc_admin_client_secret_guard_prod_raises(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a missing or placeholder KC admin client secret must abort startup."""
    # Arrange: prod with valid Supabase key so that only KC secret is tested
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    # Placeholder secret must be rejected
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_bff_internal_shared_secret_guard_prod_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, BFF_INTERNAL_SHARED_SECRET must be configured explicitly."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.delenv("BFF_INTERNAL_SHARED_SECRET", raising=False)

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_bff_internal_shared_secret_guard_prod_rejects_placeholder(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, placeholder BFF_INTERNAL_SHARED_SECRET values must be rejected."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_kc_admin_client_secret_guard_dev_allows_placeholder(monkeypatch: pytest.MonkeyPatch):
    """In dev env, a placeholder KC admin client secret is tolerated for local setups."""
    monkeypatch.setenv("GUSTAV_ENV", "dev")
    # Dev also tolerates dummy Supabase
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DUMMY_DO_NOT_USE")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    # Should not raise
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_prod_requires_storage_verify_and_disables_proxy(monkeypatch: pytest.MonkeyPatch):
    """Prod-like env must enforce storage verify and forbid dev upload stub/proxy."""
    # Base valid prod env
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_SECRET")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "real-internal-h5p-secret")
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )
    monkeypatch.delenv("REQUIRE_STORAGE_VERIFY", raising=False)

    from backend.web import config as cfg  # type: ignore
    import importlib
    importlib.reload(cfg)

    # 1) REQUIRE_STORAGE_VERIFY missing/false must raise
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()

    # 2) When REQUIRE_STORAGE_VERIFY=true, but dev upload stub enabled, must raise
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()

    # 3) When REQUIRE_STORAGE_VERIFY=true, but storage upload proxy enabled, must raise
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()

    # 4) When all guards satisfied, should not raise
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    importlib.reload(cfg)
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_prod_forbids_auto_create_storage_buckets(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, AUTO_CREATE_STORAGE_BUCKETS=true must abort startup."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_SECRET")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "real-internal-h5p-secret")
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )
    # The new guard must reject this setting in prod-like envs
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")

    from backend.web import config as cfg  # type: ignore
    import importlib
    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_h5p_review_token_secret_guard_prod_raises(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a missing/placeholder H5P review token secret must abort startup."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_SECRET")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )

    # Placeholder must be rejected.
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_h5p_review_token_secret_guard_prod_allows_real_secret(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a non-placeholder H5P review token secret is allowed."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "REAL_NON_DUMMY")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_SECRET")
    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "real-bff-secret")
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "real-internal-h5p-secret")
    monkeypatch.setenv("KC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("KC_PUBLIC_BASE_URL", "https://id.example.com")
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "false")
    monkeypatch.setenv("H5P_REVIEW_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://gustav_app:strong@db.example.com:5432/postgres?sslmode=require",
    )

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_h5p_internal_shared_secret_guard_prod_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, the Web service must fail fast without the H5P internal shared secret."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.delenv("H5P_INTERNAL_SHARED_SECRET", raising=False)

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit, match="H5P_INTERNAL_SHARED_SECRET"):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_h5p_internal_shared_secret_guard_prod_rejects_placeholder(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, placeholder H5P internal shared secrets must be rejected."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.setenv("H5P_INTERNAL_SHARED_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit, match="H5P_INTERNAL_SHARED_SECRET"):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_app_csrf_token_secret_guard_prod_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, APP_CSRF_TOKEN_SECRET must be configured explicitly."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.delenv("APP_CSRF_TOKEN_SECRET", raising=False)

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_app_csrf_token_secret_guard_prod_rejects_placeholder(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, placeholder APP_CSRF_TOKEN_SECRET values must be rejected."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "CHANGE_ME_DEV")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    with pytest.raises(SystemExit):
        cfg.ensure_secure_config_on_startup()


@pytest.mark.anyio
async def test_app_csrf_token_secret_guard_prod_allows_real_secret(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, a non-placeholder APP_CSRF_TOKEN_SECRET is allowed."""
    _set_minimal_prod_env(monkeypatch)
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "real-csrf-secret")

    from backend.web import config as cfg  # type: ignore

    importlib.reload(cfg)
    cfg.ensure_secure_config_on_startup()
