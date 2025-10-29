# Legacy → Alpha2 Migration Script Plan (2025-10-28)

## 1. Context & Goal
- Legacy Supabase holds production data (courses, units, submissions, storage blobs) that must be migrated into the Alpha2 schema described in `docs/migration/legacy_data_import_plan.md`.
- Identified artefacts now available in `gustav-alpha2`: database schema/migration history, storage blob archive under `docs/backups/storage_blobs_2025-10-28_13-13-13.tar.gz`, and comprehensive runbook guidance.
- Objective: design and implement a script (or small toolchain) that performs a repeatable, auditable migration using TDD and Clean Architecture principles.

## 2. Scope
- In-scope: automate the full path from loading legacy data (DB dump + storage blobs) into staging tables through to Alpha2 inserts, including validation, audit logging, and resumable batches.
- Out-of-scope: migration of intentionally discarded artefacts (mastery tables, legacy queue data) and post-import UI adjustments.

## 3. Input Artefacts
- **Database dump**: `legacy-code-alpha1/backups/db_backup_2025-09-25_18-15-07.sql.gz` (primary) plus later snapshots for verification.
- **Storage blobs**: `docs/backups/storage_blobs_2025-10-28_13-13-13.tar.gz` (contains `section_materials` + `submissions` buckets).
- **User mapping**: `legacy-code-alpha1/backend/tools/legacy_user_import.py` generates `legacy_user_map`.
- **Schema reference**: Alpha2 migrations inside `supabase/migrations/` and glossary definitions.

## 4. Proposed Architecture
- **Driver layer**: Python CLI (`backend/tools/legacy_migration.py`) orchestrating steps; obey Clean Architecture by delegating DB/IO to adapters.
- **Adapters**:
  - PostgreSQL adapter using SQLAlchemy or psycopg for transactional batches.
  - Storage adapter reading from extracted blob directory (default `/tmp/legacy_storage`, configurable).
  - Audit writer capturing JSON reports per entity (`import_audit_runs`, file outputs).
- **Use cases (interactors)** matching migration phases: identity mapping, courses/memberships, units/modules, sections/releases, materials, tasks, submissions.
- **Configuration** via `.env` or CLI flags (paths, batch sizes, dry-run toggle).

## 5. Implementation Outline
1. CLI skeleton supporting `--dry-run`, `--resume <run-id>`, `--storage-path`, `--db-dsn`.
2. Shared utilities for:
   - Loading legacy → new ID mappings.
   - Normalising timestamps, criteria arrays, released_by fallback logic.
   - Reading blob files and hashing content (SHA-256).
3. For each entity group:
   - Fetch data from staging (or live legacy DB) in batches.
   - Transform to Alpha2 contract (using glossary terminology).
   - Persist via repository layer with idempotent UPSERTs (`ON CONFLICT`).
   - Record successes/failures in audit tables with error categories (`ambiguous_course`, etc.).
4. Summary report generation (JSON + stdout) mirroring KPI checks from the runbook.

## 6. Testing Strategy
- Follow TDD (Red-Green-Refactor) per feature:
  - Dedicated suite under `backend/migration_tests/` with fixtures spinning up a temporary Alpha2 DB (Supabase test profile).
  - Use sample slices of the DB dump (or synthetic fixtures) to trigger Happy Path, edge cases (first/last positions), and error handling scenarios.
  - Mock storage adapter when isolating DB logic; add integration test that reads actual blob files from extracted archive.
- Provide a helper command (e.g. `scripts/test_legacy_migration.sh`) so the suite runs independently of the main `.venv/bin/pytest -q` pipeline.
- Continuous dry-run tests in CI to ensure idempotence (no writes when `--dry-run` set).

## 7. Tooling & Dependencies
- Python 3.12 (match project interpreter).
- Libraries: `psycopg[binary]` or `asyncpg`, `click` (CLI), `pandas` optionally for CSV transformations (TBD).
- Reuse existing Supabase Docker stack for local verification; document ports (Alpha2 uses defaults, legacy tool may target alternate port `55322`).

## 8. Risks & Mitigations
- **Large dataset** → implement streaming batches & progress checkpoints.
- **Ambiguous submissions** → enforce resolver logic, auto-skip with audit entries.
- **Blob-path mismatches** → cross-check SHA-256 and size before insert; skip on mismatch.
- **RLS violations** → run with service-role credentials; verify `set local app.current_sub` fallback.

## 9. Open Questions
- Preferred environment for running migration (local workstation vs CI runner vs dedicated server)?
- Should we maintain staging tables inside Alpha2 DB or a separate schema (`legacy_staging`)? 
- How to distribute the heavy artefacts after merge (leave in repo vs external artifact store)?

## 10. Next Steps
1. Confirm staging strategy (restore DB dump to local Supabase vs connect to legacy instance).
2. Define Behaviour-Driven (Given-When-Then) scenarios for first use case (identity mapping import).
3. Draft pytest failing test targeting API endpoint or CLI interface.
4. Implement minimal code to satisfy first test, iterating through migration phases.

## 11. User Story (Felix · Product Owner)
> As Felix, I want the migration tool to recreate the legacy user identity map in Alpha2 so that every migrated course, module, or submission can reference the correct teacher and student accounts without manual reconciliation.

### Acceptance Criteria
- Migration CLI can ingest the legacy user dump and populate/refresh `legacy_user_map`.
- Process is idempotent: repeated runs do not duplicate entries and report consistent statistics.
- Detailed audit output (JSON + table) highlights conflicts, skips, and missing identities.
- Dry-run mode produces the same audit data but performs no writes.

## 12. BDD Scenarios (Identity Mapping)
1. **Happy Path – new mappings created**
   - Given the legacy database contains users with unique IDs and the target Alpha2 DB exposes the `legacy_user_map` table  
   - When the migration CLI runs in normal mode with a service-role DSN  
   - Then all legacy IDs are inserted with matching `sub` values, and the audit report marks the run as `ok`.

2. **Edge Case – duplicate sub detected**
   - Given two legacy users resolve to the same new `sub`  
   - When the CLI processes the batch  
   - Then the second record is skipped, the audit run logs status `conflict` with reason `duplicate_sub`, and the command exits with a non-zero status.

3. **Error Case – insufficient privileges**
   - Given the CLI is executed with a DSN that is subject to RLS (no service role)  
   - When the identity mapping use case starts  
   - Then the command aborts, no rows are written, and the audit output reports `policy_denied`.

4. **Edge Case – idempotent rerun**
   - Given `legacy_user_map` already contains the full mapping set  
   - When the CLI is executed again in normal mode  
   - Then zero new rows are written, the audit report lists each mapping as `skip`, and the exit status is success.

5. **Error Case – dry run verification**
   - Given the CLI is launched with `--dry-run`  
   - When the identity mapping step completes  
   - Then no database writes occur, the audit JSON reflects intended inserts, and the command exits successfully.
