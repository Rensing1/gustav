# DB Test Inventory

Status: Draft
Owner: Produktverantwortlicher
Local checks: `make test-db-inventory`
CI status: `make verify` führt `make test-db-inventory` als Synchronitätscheck aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: vor dem Scharfstellen von `db_read`/`db_write` und nach größeren DB/RLS-Teständerungen

## Zweck
Dieses Inventar macht DB-, RLS-, Migrations- und Supabase-nahe Tests sichtbar, bevor `db_read` und `db_write` als harte Marker-Regel eingesetzt werden. Es verändert keine Tests und ersetzt keine Sicherheitsprüfung.

## Zusammenfassung
- Inventarisierte Dateien: 144
- Echte DB/RLS-Kandidaten ohne `db_read`/`db_write`: 97
- Echte DB/RLS-Kandidaten mit `db_read`/`db_write`: 7
- Echte DB/RLS-Kandidaten mit bestehendem Opt-in-Marker: 9
- Supabase-Storage-/Konfigurationsverträge ohne echte DB-Verbindung: 27
- Statische Migrationstests ohne echte DB-Verbindung: 4

## Marker-Regel
`missing-db-marker` ist in diesem Schritt ein Review-Signal, kein harter Fehler. Vor einer späteren Verschärfung muss jede betroffene Datei entweder `db_read`/`db_write` bekommen oder bewusst als servicefreier Contract-Test klassifiziert werden.

| Test file | Classification | Markers | Marker status | Signals | Recommended action |
| --- | --- | --- | --- | --- | --- |
| backend/tests/conftest.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, env:SESSION_TEST_DSN, env:SUPABASE_SERVICE_ROLE_KEY, psycopg-connect, psycopg-import | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_learning_worker_dspy_only_placeholder.py | real-db | - | missing-db-marker | env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py | real-db | - | missing-db-marker | psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision.py | real-db | - | missing-db-marker | psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_dev_upload_root.py | real-db | - | missing-db-marker | env:SUPABASE_SERVICE_ROLE_KEY, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_filius_fls.py | real-db | - | missing-db-marker | psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_logs.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/learning_adapters/test_local_vision_makecode_hex.py | real-db | - | missing-db-marker | psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_missing_bytes_transient.py | real-db | - | missing-db-marker | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_pdf_cached_paths.py | real-db | - | missing-db-marker | env:SUPABASE_PUBLIC_URL, env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_pdf_remote_render.py | real-db | - | missing-db-marker | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_pdf_remote_render_error.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/learning_adapters/test_local_vision_pdf_remote_wrong_content.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/learning_adapters/test_local_vision_remote_fetch.py | real-db | - | missing-db-marker | env:SUPABASE_PUBLIC_URL, env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-required, supabase | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_sb3.py | real-db | - | missing-db-marker | psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_streaming.py | real-db | - | missing-db-marker | env:SUPABASE_PUBLIC_URL, env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/learning_adapters/test_local_vision_text_passthrough.py | real-db | - | missing-db-marker | psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_ai_usage_events_security.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_concern_box_entries_rls.py | real-db | - | missing-db-marker | migration, psycopg-connect, psycopg-import, requires-db, rls | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_course_memberships_rls_delete_policy.py | real-db | db_write | marked-db | migration, psycopg-connect, psycopg-import, requires-db, rls | Keep marker and isolation visible |
| backend/tests/migration/test_import_snapshot_backup.py | migration-static | - | no-db-marker-needed | migration, supabase | Keep static migration contract unless it opens a DB connection |
| backend/tests/migration/test_keycloak_admin_sync.py | migration-static | - | no-db-marker-needed | migration | Keep static migration contract unless it opens a DB connection |
| backend/tests/migration/test_learning_material_visibility_batch_helper_contract.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_legacy_migration_batch_scope.py | migration-static | legacy_migration | no-db-marker-needed | migration | Keep static migration contract unless it opens a DB connection |
| backend/tests/migration/test_legacy_migration_cli.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_legacy_migration_courses.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_legacy_migration_materials_tasks.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_legacy_migration_modules_releases.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_legacy_migration_resume.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_legacy_migration_submissions.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_legacy_migration_units_sections.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import, requires-db | Keep existing opt-in gate |
| backend/tests/migration/test_memberships_remove_definer_owner_binding.py | real-db | db_write | marked-db | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Keep marker and isolation visible |
| backend/tests/migration/test_modular_edge_validator_exec_privileges.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_modular_unlock_helper_no_edge_n_plus_one.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_rls_exec_privileges.py | real-db | db_write | marked-db | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db, rls | Keep marker and isolation visible |
| backend/tests/migration/test_sub_mapping_sync.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import | Keep existing opt-in gate |
| backend/tests/migration/test_sub_mapping_sync_keycloak.py | real-db | legacy_migration | covered-by-opt-in-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, migration, psycopg-connect, psycopg-import | Keep existing opt-in gate |
| backend/tests/migration/test_teaching_latest_submission_owner_helper_hardening.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_teaching_live_unit_summary_helper_hardening.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_unit_module_edges_update_hardening.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/migration/test_verify_db_preflight.py | real-db | - | missing-db-marker | env:DATABASE_URL, migration | Review for db_read/db_write before marker hardening |
| backend/tests/storage/test_bootstrap_timeouts.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_STORAGE_BUCKET, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_api_cache_headers_materials_tasks.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_api_me_with_db_session_store.py | real-db | - | missing-db-marker | env:SESSION_TEST_DSN | Review for db_read/db_write before marker hardening |
| backend/tests/test_app_sessions_rls_live.py | real-db | - | missing-db-marker | env:RLS_TEST_DSN, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, rls | Review for db_read/db_write before marker hardening |
| backend/tests/test_app_storage_wiring.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_config_security.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SUPABASE_SERVICE_ROLE_KEY | Review for db_read/db_write before marker hardening |
| backend/tests/test_db_required_gate_contract.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_db_security_roles.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, psycopg-connect, psycopg-import | Review for db_read/db_write before marker hardening |
| backend/tests/test_db_session_store.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SESSION_TEST_DSN, env:SUPABASE_DB_URL | Review for db_read/db_write before marker hardening |
| backend/tests/test_filius_migrations_contract.py | migration-static | - | no-db-marker-needed | migration, supabase | Keep static migration contract unless it opens a DB connection |
| backend/tests/test_learning_api_contract.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_bucket_uses_central_config.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_calliope_hex_upload_only_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_csrf_trust_proxy.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_download_bytes_rewrites_public_host.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_h5p_access_check_api.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_h5p_access_check_index_migration.py | real-db | - | missing-db-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_h5p_scoring_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_internal_proxy_limit_config.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_internal_proxy_prod_parity.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_internal_proxy_security.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_lazy_storage_wiring.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_STORAGE_BUCKET, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_modular_units_api_contract.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_modular_unlock_parity.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_my_courses_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_pdf_persist_in_dev.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_pdf_preprocessing_usecase.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_repo_dsn_enforcement.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_repo_mark_extracted.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_repo_semantics.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_rls_owners.py | real-db | db_write | marked-db | env:DATABASE_URL, psycopg-connect, psycopg-import, requires-db, rls | Keep marker and isolation visible |
| backend/tests/test_learning_scratch_sb3_upload_only_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_sections_api_edges.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_student_rls_policies.py | real-db | db_write | marked-db | env:DATABASE_URL, env:RLS_TEST_DSN, psycopg-connect, psycopg-import, requires-db, rls | Keep marker and isolation visible |
| backend/tests/test_learning_submission_storage_verification.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_submissions_idempotency_header.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_unit_sections_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_upload_intent_public_host.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_upload_intents_behavior.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_upload_proxy_fallback.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_visual_upload_only_api.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_e2e_local.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SERVICE_ROLE_DSN, env:SUPABASE_PUBLIC_URL, env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_error_codes.py | real-db | - | missing-db-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_jobs.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_pdf_extracted_flow.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_privacy_logs.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SERVICE_ROLE_DSN, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_queue_legacy.py | storage-or-config | - | no-db-marker-needed | supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_learning_worker_security.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_task_context.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_text_bypass_vision.py | real-db | - | missing-db-marker | env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_transaction_boundaries.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_learning_worker_visual_dspy_pipeline.py | real-db | - | missing-db-marker | env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, psycopg-required, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_storage_bootstrap.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_STORAGE_BUCKET, env:SUPABASE_URL | Keep service-free unless it reaches the real DB |
| backend/tests/test_storage_buckets_provisioning.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, migration, psycopg-connect, psycopg-import, supabase | Review for db_read/db_write before marker hardening |
| backend/tests/test_storage_config_defaults.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_STORAGE_BUCKET | Keep service-free unless it reaches the real DB |
| backend/tests/test_storage_public_url_rewrite.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_storage_supabase_adapter.py | storage-or-config | - | no-db-marker-needed | supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_storage_verification_streaming_security.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_supabase_storage_adapter.py | storage-or-config | - | no-db-marker-needed | supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_supabase_storage_e2e.py | storage-or-config | supabase_integration | no-db-marker-needed | env:SUPABASE_SERVICE_ROLE_KEY, env:SUPABASE_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_supabase_storage_head_security.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_supabase_storage_head_timeout.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_PUBLIC_URL, supabase | Keep service-free unless it reaches the real DB |
| backend/tests/test_teaching_course_existence_helpers_optional.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_courses_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_courses_update_delete_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_courses_update_semantics.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_detail_api.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_detail_relation_guard.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_student_overview_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_unit_delta_api.py | real-db | - | missing-db-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_unit_summary_api.py | real-db | - | missing-db-marker | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_unit_summary_legacy_email_fallback.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_live_unit_summary_names_humanized.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_materials_bucket_uses_central_config.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_STORAGE_BUCKET | Keep service-free unless it reaches the real DB |
| backend/tests/test_teaching_materials_files_api.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_materials_markdown_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_members_api_default_limit.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_members_semantics.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_memberships_delete_rls_policy.py | real-db | db_write | marked-db | env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, env:SESSION_TEST_DSN, requires-db, rls | Keep marker and isolation visible |
| backend/tests/test_teaching_modular_unit_editor_crud_api_contract.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_modular_unit_graph_api_contract.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_module_section_releases_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_module_sections_list_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_module_sections_releases_headers.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_repo_db_optional.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import, rls | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_repo_dsn_enforcement.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, env:SUPABASE_DB_URL, psycopg-import | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_rls_policies_optional.py | real-db | db_write | marked-db | env:DATABASE_URL, env:RLS_TEST_DSN, psycopg-connect, psycopg-import, requires-db, rls | Keep marker and isolation visible |
| backend/tests/test_teaching_section_id_immutability_db_contract.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_section_visibility_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_sections_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_sections_concurrency_edge.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_sections_reorder_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_sections_rls_db.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, rls | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_tasks_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_tasks_h5p_visual_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_unit_phases_api.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_units_modules_api.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_SERVICE_DSN, env:SERVICE_ROLE_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_units_sections_guard_order.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_upload_intents_limits_and_keys.py | storage-or-config | - | no-db-marker-needed | env:SUPABASE_STORAGE_BUCKET | Keep service-free unless it reaches the real DB |
| backend/tests/test_teaching_visibility_csrf.py | real-db | - | missing-db-marker | requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_teaching_visibility_db_constraints.py | real-db | - | missing-db-marker | env:DATABASE_URL, env:RLS_TEST_DSN, psycopg-connect, psycopg-import, requires-db | Review for db_read/db_write before marker hardening |
| backend/tests/test_testing_environment_guards.py | real-db | - | missing-db-marker | env:SERVICE_ROLE_DSN, supabase | Review for db_read/db_write before marker hardening |
| backend/tests/utils/db.py | real-db | - | missing-db-marker | env:DATABASE_URL, psycopg-connect, psycopg-import | Review for db_read/db_write before marker hardening |

## Offene Arbeit
- `missing-db-marker`-Dateien in kleine Review-Batches aufteilen.
- Danach entscheiden, ob `db_read` und `db_write` harte Marker oder ersetzbare Übergangsmarker sind.
- Tests mit globalen DB-Mutationen getrennt von isolierten DB-Lese-/Schreibtests behandeln.
