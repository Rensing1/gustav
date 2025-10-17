FROM quay.io/keycloak/keycloak:24.0

# Copy the custom GUSTAV login theme into the Keycloak image
# This makes deployments reproducible without runtime volumes.
COPY keycloak/themes/gustav /opt/keycloak/themes/gustav

# Copy the canonical app CSS into the theme so the IdP UI shares styling
# with the main app without a bind mount.
COPY backend/web/static/css/gustav.css /opt/keycloak/themes/gustav/login/resources/css/app-gustav-base.css

# Optionally bake the realm import for reproducible local/prod setups.
# Keycloak will import this on first run with `--import-realm`.
COPY keycloak/realm-gustav.json /opt/keycloak/data/import/realm-gustav.json

# No ENTRYPOINT/CMD changes: compose provides `start-dev --import-realm`.

