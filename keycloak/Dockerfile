FROM gradle:8.14-jdk21 AS bcrypt-provider
ARG KEYCLOAK_BCRYPT_VERSION=1.7.0
WORKDIR /provider
RUN curl --fail --location "https://github.com/leroyguillaume/keycloak-bcrypt/archive/refs/tags/v${KEYCLOAK_BCRYPT_VERSION}.tar.gz" \
    --output /tmp/keycloak-bcrypt.tar.gz \
 && echo "ab54105d5ff610ad5d4de1003788847cfb2924debd859c4374739425b847c671  /tmp/keycloak-bcrypt.tar.gz" | sha256sum --check - \
 && tar -xzf /tmp/keycloak-bcrypt.tar.gz --strip-components=1 \
 && gradle --no-daemon test jar -Pdependency.keycloak.version=26.8.1

FROM node:24.22.1-alpine AS auth-fonts
WORKDIR /fonts
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM python:3.11.17-slim AS realm-renderer
ARG ALLOWED_REGISTRATION_DOMAINS=
WORKDIR /work
COPY keycloak/realm-gustav.json /work/realm-gustav.json
COPY keycloak/render_realm.py /work/render_realm.py
RUN python /work/render_realm.py \
    --input /work/realm-gustav.json \
    --output /work/realm-gustav.rendered.json \
    --allowed-registration-domains "${ALLOWED_REGISTRATION_DOMAINS}"

FROM quay.io/keycloak/keycloak:26.8.1

# Provider versions
ARG KEYCLOAK_BCRYPT_VERSION=1.7.0

# Copy the custom GUSTAV login theme into the Keycloak image
# This makes deployments reproducible without runtime volumes.
# Ignore checkout read bits: directories need traversal, files need runtime reads.
# Keep root ownership so the non-root server cannot rewrite theme resources.
COPY --chown=0:0 --chmod=u=rwX,go=rX keycloak/themes/gustav /opt/keycloak/themes/gustav

# Copy the shared auth stylesheet into the theme so Svelte entry pages and
# Keycloak-hosted flows speak the same visual language without runtime mounts.
COPY --chown=0:0 --chmod=0644 frontend/src/lib/styles/auth-theme.css /opt/keycloak/themes/gustav/login/resources/css/auth-theme.css
COPY --chown=0:0 --chmod=0644 frontend/src/lib/styles/theme-tokens.css /opt/keycloak/themes/gustav/login/resources/css/theme-tokens.css
# Reuse the locked font packages including their licences; no cross-origin font requests.
COPY --from=auth-fonts --chown=0:0 --chmod=u=rwX,go=rX /fonts/node_modules/@fontsource/inter /opt/keycloak/themes/gustav/login/resources/fonts/inter
COPY --from=auth-fonts --chown=0:0 --chmod=u=rwX,go=rX /fonts/node_modules/@fontsource/space-grotesk /opt/keycloak/themes/gustav/login/resources/fonts/space-grotesk

# Install bcrypt password hash provider so imported Supabase hashes remain valid.
# Source: https://github.com/leroyguillaume/keycloak-bcrypt (Apache-2.0)
# Version 1.7.0 still uses the internal password-hashing SPI (server-spi-private).
# Recheck the provider build and both isolated login smokes before a major upgrade.
COPY --from=bcrypt-provider /provider/build/libs/keycloak-bcrypt-${KEYCLOAK_BCRYPT_VERSION}.jar /opt/keycloak/providers/keycloak-bcrypt-${KEYCLOAK_BCRYPT_VERSION}.jar

# Bake a rendered realm import from the shared registration-domain config.
# Keycloak will import this on first run with `--import-realm`.
COPY --from=realm-renderer /work/realm-gustav.rendered.json /opt/keycloak/data/import/realm-gustav.json

# Build Keycloak in optimized mode for PostgreSQL so that
# the production `start --optimized` command uses Postgres
# instead of the default H2 configuration.
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# No ENTRYPOINT/CMD changes: docker-compose provides the
# `start --optimized --import-realm` command at runtime.
