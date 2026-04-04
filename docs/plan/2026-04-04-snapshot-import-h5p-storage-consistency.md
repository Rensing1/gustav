# Snapshot Import H5P Storage Consistency

## Summary
- Local snapshot restore currently rebuilds the database and Supabase storage buckets, but not the separate H5P filesystem storage under `supabase/storage/h5p`.
- This can leave learner pages with valid `unit_tasks.h5p_content_id` references while the referenced H5P content directory is missing.
- The result is a learner-visible H5P player error: `Error loading H5P content from server: not_found`.

## Intended Behavior
- Snapshot restore accepts an additional optional archive `h5p_storage.tar.gz`.
- When present, the importer restores the archive into `supabase/storage/h5p`.
- After DB restore, the importer validates that every referenced `unit_tasks.h5p_content_id` exists in the restored H5P storage.
- If a snapshot references H5P content but does not contain the required files, the importer fails fast with a clear diagnostic instead of silently restoring a broken local environment.

## Tests First
- Extend `backend/tests/migration/test_import_snapshot_backup.py` so `resolve_snapshot_files(...)` recognizes `h5p_storage.tar.gz`.
- Add tests for restoring `h5p_storage.tar.gz` into the local H5P storage root.
- Add tests for the post-restore consistency check:
  - success when no H5P tasks exist
  - success when all referenced content directories exist
  - failure when at least one referenced content directory is missing
- Add `main()` tests for:
  - successful restore with optional H5P archive
  - fail-fast behavior when the archive is missing but restored DB rows reference H5P content

## Implementation Notes
- Keep the existing HTTP/runtime contracts unchanged; the issue is restore-time data consistency, not API behavior.
- Preserve backward compatibility for snapshots without `keycloak_db.sql.gz`.
- Preserve backward compatibility for snapshots without `h5p_storage.tar.gz` only when no H5P content is referenced in restored data.
