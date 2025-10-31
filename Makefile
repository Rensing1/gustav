SHELL := /bin/bash

# Defaults (can be overridden by environment)
APP_DB_USER ?= gustav_app
APP_DB_PASSWORD ?= CHANGE_ME_DEV
DB_HOST ?= 127.0.0.1
DB_PORT ?= 54322
DB_SUPERUSER ?= postgres
DB_SUPERPASSWORD ?= postgres

.PHONY: help
help:
	@echo "Targets:"
	@echo "  up                 - Build and start docker services (web, keycloak, caddy)"
	@echo "  ps                 - Show docker compose services"
	@echo "  db-login-user      - Create/alter app DB login (IN ROLE gustav_limited)"
	@echo "  test               - Run test suite (unit/integration)"
	@echo "  test-e2e           - Run E2E tests (requires running services)"
	@echo "  supabase-status    - Show local Supabase status"

.PHONY: up
up:
	docker compose up -d --build

.PHONY: ps
ps:
	docker compose ps

.PHONY: db-login-user
db-login-user:
	@echo "Creating/ensuring role $(APP_DB_USER) IN ROLE gustav_limited ..."
	@APP_DB_USER=$(APP_DB_USER) APP_DB_PASSWORD=$(APP_DB_PASSWORD) \
		PGPASSWORD=$(DB_SUPERPASSWORD) psql -h $(DB_HOST) -p $(DB_PORT) -U $(DB_SUPERUSER) -d postgres -v ON_ERROR_STOP=1 \
		-v app_user="$(APP_DB_USER)" -v app_pass="$(APP_DB_PASSWORD)" \
		-f scripts/dev/create_login_user.sql >/dev/null
	@echo "Done. Example DSN: postgresql://$(APP_DB_USER):<secret>@$(DB_HOST):$(DB_PORT)/postgres"

.PHONY: test
test:
	. ./.venv/bin/activate && pytest -q

.PHONY: test-e2e
test-e2e:
	. ./.venv/bin/activate && RUN_E2E=1 pytest -q -m e2e

.PHONY: supabase-status
supabase-status:
	supabase status
