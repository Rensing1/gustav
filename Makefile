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
	@echo "  reset-local        - Reset local Supabase DB + recreate app services"
	@echo "  db-login-user      - Create/alter app DB login (IN ROLE gustav_limited, local only)"
	@echo "  test               - Run test suite (unit/integration)"
	@echo "  verify-preflight-db - Check DB schema prerequisites for make verify"
	@echo "  test-e2e           - Run E2E tests (requires running services)"
	@echo "  test-openai        - Run OpenAI endpoint smoke tests (requires local inference endpoint)"
	@echo "  supabase-status    - Show local Supabase status"
	@echo "  verify             - Run all test suites (unit + integrations + e2e)"
	@echo "  import-legacy      - Import legacy Supabase dump into local DB"
	@echo "  import-legacy-dry  - Dry-run legacy import (no writes)"
	@echo "  import-snapshot    - Import snapshot backup (DB + storage + optional H5P storage) into local Supabase"
	@echo "  import-snapshot-dry - Dry-run snapshot import (no writes)"
	@echo "  keycloak-admin-sync - Sync Keycloak admin client secret + admin password to .env values"
	@echo "  keycloak-admin-reset - Force reset/recreate local Keycloak admin user (requires --yes in tool)"
	@echo "  docker-validate    - Validate docker compose config (catches syntax/vars)"

.PHONY: up
up:
	mkdir -p .tmp/dev_uploads
	mkdir -p .tmp
	touch .tmp/caddy-root.crt
	docker compose up -d --build
	# Best-effort: copy Caddy internal root CA for HTTPS clients (e.g. E2E tests).
	@if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi

.PHONY: ps
ps:
	docker compose ps

.PHONY: reset-local
reset-local:
	# Reset Supabase DB (non-interactive), then restore required local invariants:
	# - app login role IN ROLE gustav_limited
	# - recreate services that consume env_file (.env)
	supabase db reset --yes
	$(MAKE) db-login-user
	@echo "Note: Supabase keys rotate on db reset. Update SUPABASE_SERVICE_ROLE_KEY in .env from: supabase status"
	mkdir -p .tmp/dev_uploads
	mkdir -p .tmp
	touch .tmp/caddy-root.crt
	docker compose up -d --build --force-recreate web learning-worker h5p
	# Best-effort: copy Caddy internal root CA for HTTPS clients (e.g. E2E tests).
	@if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi

.PHONY: db-login-user
db-login-user:
	@echo "Creating/ensuring role $(APP_DB_USER) IN ROLE gustav_limited ..."
	@set -euo pipefail; \
	  printf '%s\n' \
	    "\\getenv app_db_user APP_DB_USER" \
	    "\\getenv app_db_password APP_DB_PASSWORD" \
	    "SELECT format('CREATE ROLE %I WITH LOGIN PASSWORD %L', :'app_db_user', :'app_db_password')" \
	    "  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_db_user');" \
	    "\\gexec" \
	    "SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'app_db_user', :'app_db_password');" \
	    "\\gexec" \
	    "SELECT format('GRANT gustav_limited TO %I', :'app_db_user');" \
	    "\\gexec" \
	  | APP_DB_USER="$(APP_DB_USER)" APP_DB_PASSWORD="$(APP_DB_PASSWORD)" PGPASSWORD="$(DB_SUPERPASSWORD)" \
	    psql -q -h $(DB_HOST) -p $(DB_PORT) -U $(DB_SUPERUSER) -d postgres -v ON_ERROR_STOP=1 >/dev/null
	@echo "Done. Example DSN: postgresql://$(APP_DB_USER):<secret>@$(DB_HOST):$(DB_PORT)/postgres"

.PHONY: test
test:
	. ./.venv/bin/activate && pytest -q

.PHONY: verify-preflight-db
verify-preflight-db:
	. ./.venv/bin/activate && python -m backend.tools.verify_db_preflight

.PHONY: test-h5p
test-h5p:
	# Run Node unit tests for the H5P sidecar.
	# Dependencies are installed from `package-lock.json` (not from vendored `node_modules/`).
	@cd h5p-service && [ -d node_modules ] || npm ci --omit=dev
	@cd h5p-service && npm test

.PHONY: test-e2e
test-e2e:
	# E2E requires running docker services with prod-like config (dev=prod):
	# - GUSTAV_ENV=prod (startup guards enabled)
	# - Keycloak admin API via client_credentials (KC_ADMIN_CLIENT_SECRET)
	# - Caddy local CA trusted for HTTPS endpoints
	mkdir -p .tmp/dev_uploads
	mkdir -p .tmp
	touch .tmp/caddy-root.crt
	@$(MAKE) up
	# Reload env changes into containers that depend on `.env` substitutions.
	# (e.g. prod-guards require non-placeholder secrets for both web and h5p.)
	docker compose up -d --build --force-recreate web h5p
	# Best-effort: refresh Caddy internal root CA for HTTPS clients (e.g. E2E tests).
	@if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi
	# Keep local Keycloak admin credentials deterministic after snapshot restores.
	@$(MAKE) keycloak-admin-sync
	# Optional: fail fast when the app isn't reachable yet (ignore TLS verification).
	@for i in {1..40}; do \
	  curl -skf https://app.localhost/health >/dev/null 2>&1 && break; \
	  sleep 0.5; \
	done
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && RUN_E2E=1 REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt E2E_READY_TIMEOUT_S=20 pytest -q -m e2e

.PHONY: supabase-status
supabase-status:
	supabase status

# --- Supabase integration tests ---------------------------------------------
.PHONY: test-supabase
test-supabase:
	# Run tests gated behind RUN_SUPABASE_E2E=1 and the supabase_integration marker.
	# Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set (e.g. via .env).
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && \
	RUN_SUPABASE_E2E=1 \
	SUPABASE_REWRITE_SIGNED_URL_HOST=true \
	AUTO_WIRE_STORAGE_E2E=true \
	pytest -q -m supabase_integration

.PHONY: test-openai
test-openai:
	# Smoke-test a real OpenAI-compatible endpoint (default: local Ollama on :11434).
	# Default model is `ministral-3:3b` for all variants; override via OPENAI_E2E_MODEL.
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && \
	RUN_OPENAI_E2E=1 \
	OPENAI_E2E_ROOT=$${OPENAI_E2E_ROOT:-http://localhost:11434} \
	OPENAI_E2E_MODEL=$${OPENAI_E2E_MODEL:-ministral-3:3b} \
	AI_TEXT_MODEL=$${OPENAI_E2E_MODEL} \
	AI_OCR_MODEL=$${OPENAI_E2E_MODEL} \
	AI_VISUAL_MODEL=$${OPENAI_E2E_MODEL} \
	pytest -q -m openai_integration

.PHONY: verify
verify:
	@$(MAKE) verify-preflight-db
	@REQUIRE_DB_TESTS=1 $(MAKE) test
	@$(MAKE) test-h5p
	@$(MAKE) test-supabase
	@$(MAKE) test-openai
	@$(MAKE) test-e2e

# --- Legacy data import shortcuts -------------------------------------------
# Defaults (overridable):
DUMP ?= docs/migration/supabase_backup_20251101_103457.tar.gz
SNAPSHOT ?= .tmp/snapshot_backup_latest.tar.gz
# Supabase local uses `supabase_admin` as DB superuser; `postgres` is not a superuser.
# Snapshot restores need superuser privileges to drop/recreate Supabase-managed schemas.
DSN ?= postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres
SNAPSHOT_IMPORT_ARGS ?=
LEGACY_SCHEMA ?= legacy_raw
WORKDIR ?= .tmp/migration_run
SNAPSHOT_WORKDIR ?= .tmp/snapshot_import_run

# Keycloak admin/API via Caddy with proper hostname for TLS
KC_BASE_URL ?= https://id.localhost
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
	# Ensure local CA bundle from Caddy is available for Keycloak admin HTTPS
	mkdir -p .tmp; \
	touch .tmp/caddy-root.crt; \
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi; \
	KEYCLOAK_ADMIN_PASSWORD="$(KC_ADMIN_PASS)" \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
	./.venv/bin/python -m backend.tools.import_legacy_backup \
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
	# Ensure local CA bundle from Caddy is available for Keycloak admin HTTPS
	mkdir -p .tmp; \
	touch .tmp/caddy-root.crt; \
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi; \
	KEYCLOAK_ADMIN_PASSWORD="$(KC_ADMIN_PASS)" \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
	./.venv/bin/python -m backend.tools.import_legacy_backup \
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

# --- Snapshot restore (dev convenience) -------------------------------------
.PHONY: import-snapshot
ifeq ($(VERBOSE),)
.SILENT: import-snapshot import-snapshot-dry
endif
import-snapshot:
	# Auto-load .env into the environment for this target (export all)
	@set -ea; [ -f .env ] && . ./.env; set +a; \
	./.venv/bin/python -m backend.tools.import_snapshot_backup \
	  --snapshot $(SNAPSHOT) \
	  --dsn $(DSN) \
	  --workdir $(SNAPSHOT_WORKDIR) \
	  $(SNAPSHOT_IMPORT_ARGS) \
	  --verbose && \
	supabase migration up && \
	$(MAKE) db-login-user

.PHONY: import-snapshot-dry
import-snapshot-dry:
	# Auto-load .env into the environment for this target (export all)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	./.venv/bin/python -m backend.tools.import_snapshot_backup \
	  --snapshot $(SNAPSHOT) \
	  --dsn $(DSN) \
	  --workdir $(SNAPSHOT_WORKDIR) \
	  $(SNAPSHOT_IMPORT_ARGS) \
	  --dry-run \
	  --verbose

# --- Keycloak admin credential sync/reset (local) ---------------------------
.PHONY: keycloak-admin-sync keycloak-admin-reset
ifeq ($(VERBOSE),)
.SILENT: keycloak-admin-sync keycloak-admin-reset
endif
keycloak-admin-sync:
	# Auto-load .env into the environment for this target (export all)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	mkdir -p .tmp; \
	touch .tmp/caddy-root.crt; \
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi; \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
	./.venv/bin/python -m backend.tools.keycloak_admin_sync --verbose

keycloak-admin-reset:
	# Auto-load .env into the environment for this target (export all)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	mkdir -p .tmp; \
	touch .tmp/caddy-root.crt; \
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi; \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
	./.venv/bin/python -m backend.tools.keycloak_admin_sync --reset-admin-user --yes --verbose

.PHONY: docker-validate
docker-validate:
	@echo "Validating docker compose configuration...";
	@docker compose config >/dev/null && echo "OK" || (echo "docker compose config failed" >&2; exit 1)
