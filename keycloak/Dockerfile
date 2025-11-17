FROM alpine:3.20 AS bcrypt-provider
ARG KEYCLOAK_BCRYPT_VERSION=1.6.0
RUN apk add --no-cache curl \
 && curl -L "https://github.com/leroyguillaume/keycloak-bcrypt/releases/download/v${KEYCLOAK_BCRYPT_VERSION}/keycloak-bcrypt-${KEYCLOAK_BCRYPT_VERSION}.jar" \
        --output /tmp/keycloak-bcrypt-${KEYCLOAK_BCRYPT_VERSION}.jar

FROM quay.io/keycloak/keycloak:24.0

# Provider versions
ARG KEYCLOAK_BCRYPT_VERSION=1.6.0

# Copy the custom GUSTAV login theme into the Keycloak image
# This makes deployments reproducible without runtime volumes.
COPY keycloak/themes/gustav /opt/keycloak/themes/gustav

# Copy the canonical app CSS into the theme so the IdP UI shares styling
# with the main app without a bind mount.
COPY backend/web/static/css/gustav.css /opt/keycloak/themes/gustav/login/resources/css/app-gustav-base.css

# Install bcrypt password hash provider so imported Supabase hashes remain valid.
# Source: https://github.com/leroyguillaume/keycloak-bcrypt (Apache-2.0)
COPY --from=bcrypt-provider /tmp/keycloak-bcrypt-${KEYCLOAK_BCRYPT_VERSION}.jar /opt/keycloak/providers/keycloak-bcrypt-${KEYCLOAK_BCRYPT_VERSION}.jar

# Optionally bake the realm import for reproducible local/prod setups.
# Keycloak will import this on first run with `--import-realm`.
COPY keycloak/realm-gustav.json /opt/keycloak/data/import/realm-gustav.json

# Build Keycloak in optimized mode for PostgreSQL so that
# the production `start --optimized` command uses Postgres
# instead of the default H2 configuration.
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# No ENTRYPOINT/CMD changes: docker-compose provides the
# `start --optimized --import-realm` command at runtime.
