from pathlib import Path

import yaml


def load_compose():
    """Load docker-compose.yml so infra tests can assert configuration."""
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists(), "docker-compose.yml must exist for infrastructure tests"
    return yaml.safe_load(compose_path.read_text())


def _environment_lines(service: dict) -> list[str]:
    environment = service.get("environment", [])
    if isinstance(environment, dict):
        return [f"{key}={value}" for key, value in environment.items()]
    return [str(item) for item in environment]


def test_web_service_sets_container_service_role_dsn_for_storage_cleanup():
    """Teaching storage cleanup must use the Compose DB host, not localhost."""
    compose = load_compose()
    web = compose.get("services", {}).get("web")
    assert web, "web service is missing in compose file"

    service_role_lines = [
        line
        for line in _environment_lines(web)
        if line.startswith("SERVICE_ROLE_DSN=")
    ]

    assert service_role_lines, "web service must expose SERVICE_ROLE_DSN"
    assert "supabase_db_gustav-alpha2:5432" in service_role_lines[0]
    assert "127.0.0.1:54322" not in service_role_lines[0]
    assert "${SERVICE_ROLE_DSN" not in service_role_lines[0], (
        "web container SERVICE_ROLE_DSN must not be overridable by host .env "
        "because host-local 127.0.0.1 DSNs are invalid inside the container"
    )


def test_keycloak_uses_postgres_service():
    """Keycloak must rely on a dedicated Postgres 16 service with persistent storage."""
    compose = load_compose()
    services = compose.get("services", {})

    assert "keycloak-db" in services, "Expected dedicated postgres service for Keycloak"

    keycloak_db = services["keycloak-db"]
    assert keycloak_db.get("image") == "postgres:16", "Keycloak DB should use postgres:16 image"
    assert any(
        "keycloak_pg_data" in str(volume) for volume in keycloak_db.get("volumes", [])
    ), "Keycloak DB needs persistent volume keycloak_pg_data"

    healthcheck = keycloak_db.get("healthcheck")
    assert healthcheck, "Keycloak DB should define a healthcheck"
    assert any("pg_isready" in str(cmd_part) for cmd_part in healthcheck.get("test", []))

    volumes = compose.get("volumes", {})
    assert "keycloak_pg_data" in volumes, "Persistent volume for Postgres must be declared"


def test_keycloak_configures_postgres_connection():
    """Keycloak configuration must point to the Postgres service and avoid legacy volumes."""
    compose = load_compose()
    services = compose.get("services", {})

    keycloak = services.get("keycloak")
    assert keycloak, "Keycloak service is missing in compose file"

    depends_on = keycloak.get("depends_on", [])
    depends_targets = depends_on if isinstance(depends_on, list) else depends_on.keys()
    assert "keycloak-db" in depends_targets, "Keycloak must depend on keycloak-db service"
    if isinstance(depends_on, dict):
        condition = depends_on["keycloak-db"].get("condition")
        assert condition == "service_healthy", "Dependency should wait for healthy database"

    environment = keycloak.get("environment", {})
    assert environment.get("KC_DB") == "postgres"
    assert environment.get("KC_DB_URL") == "jdbc:postgresql://keycloak-db:5432/keycloak"
    assert environment.get("KC_DB_USERNAME") == "${KC_DB_USERNAME:-keycloak}"
    assert environment.get("KC_DB_PASSWORD") == "${KC_DB_PASSWORD:-keycloak}"
    assert environment.get("KC_DB_URL_PROPERTIES") == "${KC_DB_URL_PROPERTIES:-sslmode=disable}"

    assert "volumes" not in keycloak or not keycloak["volumes"], (
        "Keycloak should no longer rely on local keycloak_data volume; persistence lives in Postgres"
    )


def test_keycloak_uses_explicit_xforwarded_proxy_headers():
    """Keycloak must trust Caddy's forwarded HTTPS headers in local=prod deployments."""
    compose = load_compose()
    keycloak = compose.get("services", {}).get("keycloak")
    assert keycloak, "Keycloak service is missing in compose file"

    environment = keycloak.get("environment", {})

    assert "KC_PROXY" not in environment, "Deprecated KC_PROXY must not hide the effective proxy contract"
    assert environment.get("KC_PROXY_HEADERS") == "xforwarded"
    assert environment.get("KC_HTTP_ENABLED") == "true"


def test_caddy_hardens_keycloak_set_cookie_headers():
    """The IdP reverse proxy should enforce the same cookie flags as the app stack."""
    caddyfile = Path("reverse-proxy/Caddyfile").read_text(encoding="utf-8")

    assert "id.localhost:443" in caddyfile
    assert "header_down Set-Cookie" in caddyfile
    assert "Secure; SameSite=Lax" in caddyfile


def test_caddy_uses_one_shared_72_hour_local_tls_policy():
    """Local hosts should renew one consistent certificate policy less often."""
    caddyfile = Path("reverse-proxy/Caddyfile").read_text(encoding="utf-8")

    assert caddyfile.count("(local_tls) {") == 1
    assert caddyfile.count("issuer internal") == 1
    assert caddyfile.count("lifetime 72h") == 1
    assert "tls internal" not in caddyfile

    for host in ("app.localhost", "localhost", "id.localhost", "supabase.localhost"):
        assert f"{host}:443 {{\n  import local_tls" in caddyfile

    assert caddyfile.count("import local_tls") == 4


def test_keycloak_configures_smtp_via_env_vars():
    """Keycloak must be wired for SMTP via explicit env vars.

    Why:
        We rely on Keycloak to send verification and password reset emails.
        The docker-compose service should therefore expose the Quarkus-based
        email sender settings via KC_SPI_EMAIL_SENDER_DEFAULT_* variables.
    """
    compose = load_compose()
    services = compose.get("services", {})

    keycloak = services.get("keycloak")
    assert keycloak, "Keycloak service is missing in compose file"

    environment = keycloak.get("environment", {})
    # Minimal contract: all core SMTP-related knobs must be present so that
    # local and production deployments can configure email uniformly.
    required_keys = [
        "KC_SPI_EMAIL_SENDER_DEFAULT_HOST",
        "KC_SPI_EMAIL_SENDER_DEFAULT_PORT",
        "KC_SPI_EMAIL_SENDER_DEFAULT_FROM",
        "KC_SPI_EMAIL_SENDER_DEFAULT_FROM_DISPLAY_NAME",
        "KC_SPI_EMAIL_SENDER_DEFAULT_USERNAME",
        "KC_SPI_EMAIL_SENDER_DEFAULT_PASSWORD",
        "KC_SPI_EMAIL_SENDER_DEFAULT_AUTH",
        "KC_SPI_EMAIL_SENDER_DEFAULT_STARTTLS",
    ]
    for key in required_keys:
        assert key in environment, f"{key} must be configured on keycloak service for SMTP"


def test_keycloak_build_receives_registration_domain_whitelist():
    """Keycloak build must receive the same domain whitelist as app and BFF.

    Why:
        Self-registration should be governed by one source of truth. If the
        Keycloak image does not receive `ALLOWED_REGISTRATION_DOMAINS` during
        build/import, the IdP can drift away from FastAPI and SvelteKit.
    """
    compose = load_compose()
    services = compose.get("services", {})

    keycloak = services.get("keycloak")
    assert keycloak, "Keycloak service is missing in compose file"

    build = keycloak.get("build", {})
    args = build.get("args", {})
    assert args.get("ALLOWED_REGISTRATION_DOMAINS") == "${ALLOWED_REGISTRATION_DOMAINS:-}"
