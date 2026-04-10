# Snapshot Import: Managed Schema Filtering

## Summary
- `make import-snapshot` must continue to accept a normal full backup as input.
- The importer currently restores Supabase-managed schemas (`auth`, `storage`, `realtime`, `_realtime`, `supabase_functions`, `supabase_migrations`, `pgbouncer`) directly into the running local stack.
- That breaks local service startup because the restored internal migration tables and ownerships do not match the local Supabase service roles.

## Implementation
- Keep the snapshot archive format unchanged.
- Keep the existing destructive reset for local restore, but do not replay service-managed Supabase schemas from the dump.
- Treat the SQL dump as a mixed source:
  - replay app-relevant schemas such as `public`, `legacy_raw`, `extensions`, `graphql`, `graphql_public`, `vault`
  - skip Supabase service-managed schemas that are expected to be bootstrapped by the local runtime
- Leave storage object upload and Keycloak restore in place.
- Make the filtering explicit in code so future schema additions are easy to review.

## Tests
- Add a regression test that verifies dump replay keeps `public.*` statements while dropping `auth.*` and `storage.*` statements from the stream.
- Add a regression test that verifies managed schema `COPY` data blocks are skipped completely, including their row payload and terminating `\.` line.
- Keep the existing importer tests green.
- Verify with:
  - `pytest -q backend/tests/migration/test_import_snapshot_backup.py`

## Assumptions
- Local UX testing depends on realistic app data and storage blobs, not on a byte-identical clone of Supabase internal migration state.
- The local stack is responsible for its own `auth` and `storage` bootstrap.
