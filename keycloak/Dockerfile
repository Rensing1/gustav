FROM gradle:8.14-jdk21 AS bcrypt-provider
ARG KEYCLOAK_BCRYPT_VERSION=1.6.0
WORKDIR /provider
RUN curl --fail --location "https://github.com/leroyguillaume/keycloak-bcrypt/archive/refs/tags/v${KEYCLOAK_BCRYPT_VERSION}.tar.gz" \
    | tar -xz --strip-components=1 \
 && gradle --no-daemon test jar -Pdependency.keycloak.version=26.7.3

FROM node:24.18.0-alpine AS auth-fonts
WORKDIR /fonts
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM python:3.12-alpine AS realm-renderer
ARG ALLOWED_REGISTRATION_DOMAINS=
WORKDIR /work
COPY keycloak/realm-gustav.json /work/realm-gustav.json
COPY keycloak/render_realm.py /work/render_realm.py
RUN python /work/render_realm.py \
    --input /work/realm-gustav.json \
    --output /work/realm-gustav.rendered.json \
    --allowed-registration-domains "${ALLOWED_REGISTRATION_DOMAINS}"

FROM quay.io/keycloak/keycloak:26.7.3

# Provider versions
ARG KEYCLOAK_BCRYPT_VERSION=1.6.0

# Copy the custom GUSTAV login theme into the Keycloak image
# This makes deployments reproducible without runtime volumes.
COPY keycloak/themes/gustav /opt/keycloak/themes/gustav

# Copy the shared auth stylesheet into the theme so Svelte entry pages and
# Keycloak-hosted flows speak the same visual language without runtime mounts.
COPY frontend/src/lib/styles/auth-theme.css /opt/keycloak/themes/gustav/login/resources/css/auth-theme.css
COPY frontend/src/lib/styles/theme-tokens.css /opt/keycloak/themes/gustav/login/resources/css/theme-tokens.css
# Reuse the locked font packages including their licences; no cross-origin font requests.
COPY --from=auth-fonts /fonts/node_modules/@fontsource/inter /opt/keycloak/themes/gustav/login/resources/fonts/inter
COPY --from=auth-fonts /fonts/node_modules/@fontsource/space-grotesk /opt/keycloak/themes/gustav/login/resources/fonts/space-grotesk

# Install bcrypt password hash provider so imported Supabase hashes remain valid.
# Source: https://github.com/leroyguillaume/keycloak-bcrypt (Apache-2.0)
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
