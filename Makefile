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
	@echo "  reset-local        - Reset Supabase DB + resync env + recreate app services"
	@echo "  db-login-user      - Create/alter app DB login (IN ROLE gustav_limited)"
	@echo "  test               - Run test suite (unit/integration)"
	@echo "  test-e2e           - Run E2E tests (requires running services)"
	@echo "  test-openai        - Run OpenAI endpoint smoke tests (requires local inference endpoint)"
	@echo "  supabase-status    - Show local Supabase status"
	@echo "  supabase-sync-env  - Sync Supabase service role key into .env"
	@echo "  prod-sync-env      - Make local .env prod-like (Keycloak+Supabase+CA sync)"
	@echo "  verify             - Run all test suites (unit + integrations + e2e)"
	@echo "  import-legacy      - Import legacy Supabase dump with Keycloak mapping"
	@echo "  import-legacy-dry  - Dry-run for the legacy import (no writes)"
	@echo "  import-legacy-all  - Full import: users (Keycloak) + data (courses, memberships, …)"
	@echo "  docker-validate    - Validate docker compose config (catches syntax/vars)"

.PHONY: up
up:
	mkdir -p .tmp/dev_uploads
	touch .tmp/caddy-root.crt
	docker compose up -d --build

.PHONY: ps
ps:
	docker compose ps

.PHONY: reset-local
reset-local:
	# Reset Supabase DB (non-interactive), then restore required local invariants:
	# - app login role IN ROLE gustav_limited
	# - fresh Supabase service role key in .env (changes on db reset)
	# - recreate services that consume env_file (.env)
	supabase db reset --yes
	$(MAKE) db-login-user
	$(MAKE) supabase-sync-env
	mkdir -p .tmp/dev_uploads
	touch .tmp/caddy-root.crt
	docker compose up -d --build --force-recreate web learning-worker h5p

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
	touch .tmp/caddy-root.crt
	@$(MAKE) up
	@$(MAKE) prod-sync-env
	# Reload env changes into containers that depend on `.env` substitutions.
	# (e.g. prod-guards require non-placeholder secrets for both web and h5p.)
	docker compose up -d --build --force-recreate web h5p
	# Fail fast when deps are broken (avoid 60s timeouts inside tests)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && E2E_READY_TIMEOUT_S=20 python3 scripts/wait_for_e2e_ready.py
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && RUN_E2E=1 E2E_READY_TIMEOUT_S=20 pytest -q -m e2e

.PHONY: supabase-status
supabase-status:
	supabase status

.PHONY: supabase-sync-env
supabase-sync-env:
	python3 scripts/sync_supabase_env.py

.PHONY: prod-sync-env
prod-sync-env:
	python3 scripts/sync_prod_env.py

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
	@REQUIRE_DB_TESTS=1 $(MAKE) test
	@$(MAKE) test-h5p
	@$(MAKE) test-supabase
	@$(MAKE) test-openai
	@$(MAKE) test-e2e

# --- Legacy data import shortcuts -------------------------------------------
# Defaults (overridable):
DUMP ?= docs/migration/supabase_backup_20251101_103457.tar.gz
DSN ?= postgresql://postgres:postgres@127.0.0.1:54322/postgres
LEGACY_SCHEMA ?= legacy_raw
WORKDIR ?= .tmp/migration_run

# Temp legacy DB (for user import from original schemas, incl. auth.users)
LEGACY_TMPDB ?= legacy_import

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
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi; \
	KEYCLOAK_ADMIN_PASSWORD="$(KC_ADMIN_PASS)" \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
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
	# Ensure local CA bundle from Caddy is available for Keycloak admin HTTPS
	mkdir -p .tmp; \
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi; \
	KEYCLOAK_ADMIN_PASSWORD="$(KC_ADMIN_PASS)" \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
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

.PHONY: import-legacy-all
ifeq ($(VERBOSE),)
.SILENT: import-legacy-all
endif
import-legacy-all:
	@echo "[1/5] Prepare CA bundle for Keycloak admin HTTPS"
	mkdir -p .tmp; \
	if docker ps --format '{{.Names}}' | grep -q '^gustav-caddy$$'; then \
	  docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt >/dev/null 2>&1 || true; \
	fi
	@echo "[2/5] Restore minimal legacy subset into temporary DB '$(LEGACY_TMPDB)' for user import"
	@chmod +x scripts/restore_legacy_subset.sh; \
	scripts/restore_legacy_subset.sh \
	  "$(DUMP)" \
	  "$(DB_HOST)" "$(DB_PORT)" "$(DB_SUPERUSER)" "$(DB_SUPERPASSWORD)" \
	  "$(LEGACY_TMPDB)" \
	  "$(WORKDIR)"
	@echo "[3/5] Import users into Keycloak from legacy DB"
	set -e; \
	set -a; [ -f .env ] && . ./.env; set +a; \
	LEGACY_DSN=postgresql://$(DB_SUPERUSER):$(DB_SUPERPASSWORD)@$(DB_HOST):$(DB_PORT)/$(LEGACY_TMPDB); \
	KC_ADMIN_USER_VAL=$${KC_ADMIN_USERNAME:-$(KC_ADMIN_USER)}; \
	KC_ADMIN_PASS_VAL=$${KC_ADMIN_PASSWORD:-$(KC_ADMIN_PASS)}; \
	# Prefer the public/base URL (id.localhost via Caddy) so host calls can resolve TLS + DNS. \
	KC_BASE_URL_VAL=$${KC_PUBLIC_BASE_URL:-https://id.localhost}; \
	KC_HOST_HEADER_VAL=$${KC_HOST_HEADER:-id.localhost}; \
	KC_REALM_VAL=$${KC_REALM:-$(KC_REALM)}; \
	KEYCLOAK_ADMIN_PASSWORD="$$KC_ADMIN_PASS_VAL" \
	KEYCLOAK_CA_BUNDLE=.tmp/caddy-root.crt \
	./.venv/bin/python -m backend.tools.legacy_user_import \
	  --legacy-dsn $$LEGACY_DSN \
	  --kc-base-url $$KC_BASE_URL_VAL \
	  --kc-host-header $$KC_HOST_HEADER_VAL \
	  --kc-admin-user $$KC_ADMIN_USER_VAL \
	  --kc-admin-pass $$KC_ADMIN_PASS_VAL \
	  --realm $$KC_REALM_VAL \
	  --force-replace
	@echo "[4/5] Import domain data (courses, memberships, units, …) into current DB"
	$(MAKE) import-legacy VERBOSE=$(VERBOSE)
	@echo "[5/5] Done. You may drop the temp DB with: dropdb -h $(DB_HOST) -p $(DB_PORT) -U $(DB_SUPERUSER) $(LEGACY_TMPDB)"

.PHONY: docker-validate
docker-validate:
	@echo "Validating docker compose configuration...";
	@docker compose config >/dev/null && echo "OK" || (echo "docker compose config failed" >&2; exit 1)
