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
	@echo "  test-ollama        - Run local Ollama connectivity tests (host: localhost:11434)"
	@echo "  test-ollama-vision - Run local Ollama Vision tests (also sets RUN_OLLAMA_VISION_E2E=1)"
	@echo "  supabase-status    - Show local Supabase status"
	@echo "  supabase-sync-env  - Sync Supabase service role key into .env"
	@echo "  import-legacy      - Import legacy Supabase dump with Keycloak mapping"
	@echo "  import-legacy-dry  - Dry-run for the legacy import (no writes)"
	@echo "  docker-validate    - Validate docker compose config (catches syntax/vars)"

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
		-f scripts/dev/create_login_user.sql >/dev/null
	@echo "Done. Example DSN: postgresql://$(APP_DB_USER):<secret>@$(DB_HOST):$(DB_PORT)/postgres"

.PHONY: test
test:
	. ./.venv/bin/activate && pytest -q

.PHONY: test-e2e
test-e2e:
	. ./.venv/bin/activate && RUN_E2E=1 pytest -q -m e2e

# --- Local Ollama integration test shortcuts ---------------------------------
# Default host URL for Ollama reachable from the host machine.
OLLAMA_URL ?= http://localhost:11434

.PHONY: test-ollama
test-ollama:
	# Auto-load .env so model names (AI_*_MODEL) are available, but override host URL.
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && \
	RUN_OLLAMA_E2E=1 \
	OLLAMA_BASE_URL=$(OLLAMA_URL) \
	pytest -q -m ollama_integration

.PHONY: test-ollama-vision
test-ollama-vision:
	# Runs vision subset as well; requires vision model to be pulled.
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && \
	RUN_OLLAMA_E2E=1 \
	RUN_OLLAMA_VISION_E2E=1 \
	OLLAMA_BASE_URL=$(OLLAMA_URL) \
	pytest -q -m ollama_integration -k vision

.PHONY: supabase-status
supabase-status:
	supabase status

.PHONY: supabase-sync-env
supabase-sync-env:
	python3 scripts/sync_supabase_env.py

# --- Supabase integration tests ---------------------------------------------
.PHONY: test-supabase
test-supabase:
	# Keep .env in sync with local Supabase (service role key), then run tests
	# that are gated behind RUN_SUPABASE_E2E=1 and the supabase_integration marker.
	# We auto-load .env so SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are exported.
	@$(MAKE) supabase-sync-env
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && \
	RUN_SUPABASE_E2E=1 \
	SUPABASE_REWRITE_SIGNED_URL_HOST=true \
	AUTO_WIRE_STORAGE_E2E=true \
	pytest -q -m supabase_integration

# --- Legacy data import shortcuts -------------------------------------------
# Defaults (overridable):
DUMP ?= docs/migration/supabase_backup_20251101_103457.tar.gz
DSN ?= postgresql://postgres:postgres@127.0.0.1:54322/postgres
LEGACY_SCHEMA ?= legacy_raw
WORKDIR ?= .tmp/migration_run

KC_BASE_URL ?= http://127.0.0.1:8100
KC_HOST_HEADER ?= id.localhost
KC_REALM ?= gustav
KC_ADMIN_USER ?= admin
KC_ADMIN_PASS ?= admin

.PHONY: import-legacy
ifeq ($(VERBOSE),)
.SILENT: import-legacy import-legacy-dry
endif
import-legacy:
	# Auto-load .env into the environment for this target (export all)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	KEYCLOAK_ADMIN_PASSWORD="$(KC_ADMIN_PASS)" \
	./.venv/bin/python scripts/import_legacy_backup.py \
	  --dump $(DUMP) \
	  --dsn $(DSN) \
	  --legacy-schema $(LEGACY_SCHEMA) \
	  --workdir $(WORKDIR) \
	  --kc-base-url $(KC_BASE_URL) \
	  --kc-host-header $(KC_HOST_HEADER) \
	  --kc-realm $(KC_REALM) \
	  --kc-admin-user $(KC_ADMIN_USER) \
	  --verbose

.PHONY: import-legacy-dry
import-legacy-dry:
	# Auto-load .env into the environment for this target (export all)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	KEYCLOAK_ADMIN_PASSWORD="$(KC_ADMIN_PASS)" \
	./.venv/bin/python scripts/import_legacy_backup.py \
	  --dump $(DUMP) \
	  --dsn $(DSN) \
	  --legacy-schema $(LEGACY_SCHEMA) \
	  --workdir $(WORKDIR) \
	  --kc-base-url $(KC_BASE_URL) \
	  --kc-host-header $(KC_HOST_HEADER) \
	  --kc-realm $(KC_REALM) \
	  --kc-admin-user $(KC_ADMIN_USER) \
	  --dry-run \
	  --verbose

.PHONY: docker-validate
docker-validate:
	@echo "Validating docker compose configuration...";
	@docker compose config >/dev/null && echo "OK" || (echo "docker compose config failed" >&2; exit 1)
