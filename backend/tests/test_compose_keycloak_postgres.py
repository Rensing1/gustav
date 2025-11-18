from pathlib import Path

import yaml


def load_compose():
    """Load docker-compose.yml so infra tests can assert configuration."""
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists(), "docker-compose.yml must exist for infrastructure tests"
    return yaml.safe_load(compose_path.read_text())


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
