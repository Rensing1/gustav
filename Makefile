SHELL := /bin/bash

# Defaults (can be overridden by environment)
APP_DB_USER ?= gustav_app
APP_DB_PASSWORD ?= CHANGE_ME_DEV
LEARNING_WORKER_DB_USER ?= gustav_worker
LEARNING_WORKER_DB_PASSWORD ?= CHANGE_ME_DEV
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
	@echo "  learning-worker-db-login-user - Create/alter worker DB login (IN ROLE gustav_worker, local only)"
	@echo "  test               - Run test suite (unit/integration)"
	@echo "  test-fast          - Run fast in-process contract/harness checks"
	@echo "  lint-backend       - Run Python lint and format checks via Ruff"
	@echo "  test-db-security   - Run DB/security-focused checks"
	@echo "  test-upload-llm-boundaries - Run upload and LLM boundary checks"
	@echo "  test-docker-image-smoke - Build and smoke-test web image without bind mounts"
	@echo "  quality-scorecard   - Generate monthly quality scorecard"
	@echo "  test-import-boundaries - Check import boundary debt against baseline"
	@echo "  test-api-contract-baseline - Check runtime /api routes against api/openapi.yml"
	@echo "  test-architecture-boundaries - Check Clean Architecture boundary debt"
	@echo "  test-route-map     - Check generated route-surface inventory"
	@echo "  test-db-inventory  - Check generated DB/RLS test inventory"
	@echo "  test-frontend-h5p  - Run frontend and H5P checks"
	@echo "  test-full-prod-like - Run full prod-like verification profile"
	@echo "  harness-minimum    - Run hard PR-1 harness safety gate"
	@echo "  harness-signals    - Run warning-only harness signals"
	@echo "  verify-preflight-db - Check DB schema prerequisites for make verify"
	@echo "  test-e2e           - Run E2E tests (requires running services)"
	@echo "  test-openai        - Run OpenAI endpoint smoke tests (requires local inference endpoint)"
	@echo "  supabase-status    - Show local Supabase status"
	@echo "  verify             - Run deterministic hard gates (unit + local build checks)"
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
	# - worker login role IN ROLE gustav_worker
	# - recreate services that consume env_file (.env)
	supabase db reset --yes
	$(MAKE) db-login-user
	$(MAKE) learning-worker-db-login-user
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

.PHONY: learning-worker-db-login-user
learning-worker-db-login-user:
	@echo "Creating/ensuring role $(LEARNING_WORKER_DB_USER) WITH dedicated worker privileges ..."
	@set -euo pipefail; \
	  printf '%s\n' \
	    "\\getenv worker_db_user LEARNING_WORKER_DB_USER" \
	    "\\getenv worker_db_password LEARNING_WORKER_DB_PASSWORD" \
	    "SELECT format('CREATE ROLE %I WITH LOGIN PASSWORD %L IN ROLE gustav_worker', :'worker_db_user', :'worker_db_password')" \
	    "  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'worker_db_user');" \
	    "\\gexec" \
	    "SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'worker_db_user', :'worker_db_password');" \
	    "\\gexec" \
	    "SELECT format('GRANT gustav_worker TO %I', :'worker_db_user')" \
	    "  WHERE :'worker_db_user' <> 'gustav_worker';" \
	    "\\gexec" \
	  | LEARNING_WORKER_DB_USER="$(LEARNING_WORKER_DB_USER)" LEARNING_WORKER_DB_PASSWORD="$(LEARNING_WORKER_DB_PASSWORD)" PGPASSWORD="$(DB_SUPERPASSWORD)" \
	    psql -q -h $(DB_HOST) -p $(DB_PORT) -U $(DB_SUPERUSER) -d postgres -v ON_ERROR_STOP=1 >/dev/null
	@echo "Done. Example DSN: postgresql://$(LEARNING_WORKER_DB_USER):<secret>@$(DB_HOST):$(DB_PORT)/postgres"

.PHONY: test
test:
	. ./.venv/bin/activate && pytest -q

.PHONY: test-fast
test-fast:
	. ./.venv/bin/activate && pytest -q \
	  backend/tests/test_harness_minimum_contract.py \
	  backend/tests/test_harness_test_strategy_docs_contract.py \
	  backend/tests/test_makefile_targets.py

.PHONY: lint-backend
lint-backend:
	@. ./.venv/bin/activate && python -c "import ruff" >/dev/null 2>&1 || { echo "Ruff is not installed. Install Python dependencies with: ./.venv/bin/python -m pip install -r backend/web/requirements.txt" >&2; exit 1; }
	. ./.venv/bin/activate && python -m ruff check backend --select F --exclude 'backend/tests/*' --exclude 'backend/tests_e2e/*'

.PHONY: test-db-security
test-db-security:
	. ./.venv/bin/activate && REQUIRE_DB_TESTS=1 pytest -q \
	  backend/tests/test_config_security.py \
	  backend/tests/test_privacy_logging_contract.py \
	  backend/tests/test_testing_environment_guards.py \
	  backend/tests/test_db_required_gate_contract.py \
	  backend/tests/test_auth_cookie_policies.py \
	  backend/tests/test_session_sync_api.py \
	  backend/tests/test_learning_submissions_default_strict_csrf.py \
	  backend/tests/test_learning_submissions_prod_csrf.py \
	  backend/tests/test_learning_csrf_trust_proxy.py \
	  backend/tests/test_learning_csrf_diag_log_redaction.py \
	  backend/tests/test_teaching_csrf_other_writes.py \
	  backend/tests/test_api_auth_unauthenticated.py \
	  backend/tests/test_bearer_jwt_auth_api.py \
	  backend/tests/test_bff_authorization_session_api.py \
	  backend/tests/test_session_bootstrap_api.py \
	  backend/tests/test_teaching_live_detail_api.py::test_latest_detail_requires_owner_and_valid_ids \
	  backend/tests/test_teaching_live_detail_api.py::test_latest_detail_fallback_respects_unit_relation \
	  backend/tests/test_teaching_live_detail_relation_guard.py \
	  backend/tests/test_learning_student_rls_policies.py \
	  backend/tests/test_learning_rls_owners.py \
	  backend/tests/test_teaching_rls_policies_optional.py \
	  backend/tests/test_teaching_memberships_delete_rls_policy.py \
	  backend/tests/migration/test_course_memberships_rls_delete_policy.py \
	  backend/tests/migration/test_memberships_remove_definer_owner_binding.py \
	  backend/tests/migration/test_rls_exec_privileges.py

.PHONY: test-upload-llm-boundaries
test-upload-llm-boundaries:
	. ./.venv/bin/activate && pytest -q \
	  backend/tests/test_upload_llm_boundaries_contract.py \
	  backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_requires_authentication \
	  backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_forbidden_for_teacher \
	  backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_csrf_violation_sets_detail \
	  backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_requires_origin_or_referer_header \
	  backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_fail_closed_when_authorization_check_unavailable \
	  backend/tests/test_teaching_upload_intents_limits_and_keys.py \
	  backend/tests/test_learning_internal_proxy_security.py \
	  backend/tests/test_learning_internal_proxy_limit_config.py \
	  backend/tests/test_storage_config_limits.py \
	  backend/tests/test_storage_key_helpers.py \
	  backend/tests/test_storage_verification_helper.py \
	  backend/tests/test_storage_verification_streaming_security.py \
	  backend/tests/test_learning_upload_content_signature_validation.py \
	  backend/tests/test_submission_content_signatures.py \
	  backend/tests/test_learning_submission_kind_guard.py \
	  backend/tests/test_learning_submission_payload_mime_casing.py \
	  backend/tests/test_learning_worker_feedback_error_mapping.py \
	  backend/tests/learning_adapters/test_feedback_program_dspy_prompt.py \
	  backend/tests/learning_adapters/test_feedback_program_dspy_structured.py \
	  backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py \
	  backend/tests/test_privacy_logging_contract.py

.PHONY: test-docker-image-smoke
test-docker-image-smoke:
	. ./.venv/bin/activate && python -m backend.tools.docker_image_smoke

.PHONY: quality-scorecard
quality-scorecard:
	. ./.venv/bin/activate && python -m backend.tools.quality_scorecard --month `date +%Y-%m` --run-docker-check

.PHONY: test-import-boundaries
test-import-boundaries:
	. ./.venv/bin/activate && python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json

.PHONY: test-api-contract-baseline
test-api-contract-baseline:
	. ./.venv/bin/activate && python -m backend.tools.openapi_contract_check --spec api/openapi.yml

.PHONY: test-architecture-boundaries
test-architecture-boundaries:
	. ./.venv/bin/activate && python -m backend.tools.architecture_boundary_scan --baseline docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json

.PHONY: test-route-map
test-route-map:
	. ./.venv/bin/activate && python -m backend.tools.route_map_inventory --check docs/harness/ROUTE_MAP.md

.PHONY: test-db-inventory
test-db-inventory:
	. ./.venv/bin/activate && python -m backend.tools.db_test_inventory --check docs/harness/DB_TEST_INVENTORY.md

.PHONY: test-frontend-h5p
test-frontend-h5p:
	@cd frontend && npm run check
	@cd frontend && npm test
	@$(MAKE) test-h5p

.PHONY: test-full-prod-like
test-full-prod-like:
	@$(MAKE) verify
	@$(MAKE) test-supabase
	@$(MAKE) test-openai
	@$(MAKE) test-e2e

.PHONY: harness-minimum
harness-minimum:
	. ./.venv/bin/activate && pytest -q \
	  backend/tests/test_harness_minimum_contract.py \
	  backend/tests/test_harness_test_strategy_docs_contract.py \
	  backend/tests/test_makefile_targets.py \
	  backend/tests/test_docker_image_smoke_contract.py \
	  backend/tests/packaging/test_import_paths_contract.py \
	  backend/tests/packaging/test_test_import_paths_contract.py \
	  backend/tests/test_import_boundary_gate_contract.py \
	  backend/tests/test_openapi_route_surface_baseline.py \
	  backend/tests/test_architecture_boundary_gate_contract.py \
	  backend/tests/test_route_map_inventory_contract.py \
	  backend/tests/test_web_security_guards_contract.py \
	  backend/tests/test_auth_flow_contract.py \
	  backend/tests/test_auth_smoke_tool_contract.py \
	  backend/tests/test_runtime_auth_helpers_contract.py \
	  backend/tests/test_auth_claims_contract.py \
	  backend/tests/test_auth_session_contract.py \
	  backend/tests/test_csrf_tokens_contract.py \
	  backend/tests/test_internal_api_client_contract.py \
	  backend/tests/test_ssr_helpers_contract.py \
	  backend/tests/test_storage_local_hash_contract.py \
	  backend/tests/test_cli_authoring_contract.py \
	  backend/tests/test_security_headers_policy_contract.py \
	  backend/tests/test_runtime_config_contract.py \
	  backend/tests/test_app_composition_contract.py \
	  backend/tests/test_legacy_retirement_contract.py \
	  backend/tests/test_legacy_html_exit_wave1_contract.py \
	  backend/tests/test_teaching_live_h5p_matrix_cell_rendering.py \
	  backend/tests/test_public_repo_safety_contract.py \
	  backend/tests/test_config_security.py \
	  backend/tests/test_privacy_logging_contract.py \
	  backend/tests/test_testing_environment_guards.py \
	  backend/tests/test_db_required_gate_contract.py \
	  backend/tests/test_openapi_no_null_type.py \
	  backend/tests/test_openapi_security_headers.py \
	  backend/tests/test_openapi_internal_flags.py
	@echo "Validating docker compose configuration..."
	@docker compose config >/dev/null && echo "OK" || (echo "docker compose config failed" >&2; exit 1)

.PHONY: harness-signals
harness-signals:
	@echo "Running warning-only harness signals. Failures are reported but do not block PR 1."
	@status=0; \
	  echo "== verify-preflight-db =="; \
	  . ./.venv/bin/activate && python -m backend.tools.verify_db_preflight || status=1; \
	  echo "== backend pytest with DB-required tests =="; \
	  . ./.venv/bin/activate && REQUIRE_DB_TESTS=1 pytest -q || status=1; \
	  echo "== frontend check =="; \
	  cd frontend && npm run check || status=1; \
	  cd ..; \
	  echo "== frontend tests =="; \
	  cd frontend && npm test || status=1; \
	  cd ..; \
	  echo "== H5P tests =="; \
	  cd h5p-service && { [ -d node_modules ] || npm ci --omit=dev; } && npm test || status=1; \
	  cd ..; \
	  echo "== docker image-only smoke =="; \
	  . ./.venv/bin/activate && python -m backend.tools.docker_image_smoke || status=1; \
	  echo "== import boundary scan =="; \
	  . ./.venv/bin/activate && python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json || status=1; \
	  echo "== docker compose config =="; \
	  docker compose config >/dev/null && echo "OK" || status=1; \
	  if [ "$$status" -ne 0 ]; then \
	    echo "Harness signals reported warnings; see output above."; \
	  else \
	    echo "Harness signals reported no warnings."; \
	  fi; \
	  exit 0

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
	# Smoke-test the OpenAI-compatible endpoint configured via OPENAI_BASE_URL.
	# Model comes from OPENAI_E2E_MODEL or AI_TEXT_MODEL in .env.
	@set -a; [ -f .env ] && . ./.env; set +a; \
	. ./.venv/bin/activate && \
	RUN_OPENAI_E2E=1 \
	pytest -q -m openai_integration

.PHONY: verify
verify:
	@$(MAKE) verify-preflight-db
	@$(MAKE) test-import-boundaries
	@$(MAKE) test-api-contract-baseline
	@$(MAKE) test-architecture-boundaries
	@$(MAKE) test-route-map
	@$(MAKE) test-db-inventory
	@$(MAKE) test-docker-image-smoke
	@REQUIRE_DB_TESTS=1 $(MAKE) test
	@$(MAKE) test-frontend-h5p

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
