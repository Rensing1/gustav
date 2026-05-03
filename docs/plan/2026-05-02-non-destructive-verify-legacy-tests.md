# Non-destructive verify: Alpha1 legacy tests retired from default suite

## Goal

`make verify` must be safe to run against the local prod-like GUSTAV stack without
clearing existing application data.

## Decision

Alpha1 legacy migration tests are no longer part of the standard verification
path. Current data restore/import work uses `make import-snapshot`, which restores
backup data from the current production-shaped system. The old Alpha1 import
tests remain available only as an explicit historical tool check.

## Implementation

- Mark old Alpha1 import tests with `pytest.mark.legacy_migration`.
- Use that marker as the single source of truth for default collection skips.
- Reject unmarked tests that contain global `TRUNCATE table public.*` cleanup.
- Allow explicit opt-in with `RUN_LEGACY_MIGRATION_TESTS=1`.
- Keep a static DB mutation safety contract so future global `TRUNCATE public.*`
  cleanup cannot re-enter the default suite unnoticed.

## Verification

- `backend/tests/test_db_mutation_safety_contract.py`
- `backend/tests/test_testing_environment_guards.py`
- A direct run of a legacy migration test should report skipped unless
  `RUN_LEGACY_MIGRATION_TESTS=1` is set.
