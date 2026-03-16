# Snapshot Import: Versioned Storage Keys

## Summary
- The live-detail file preview regression was caused by the local snapshot importer, not by teaching live SSR.
- Snapshot storage archives currently contain versioned blob files in the layout `bucket/<logical-key>/<version-uuid>`.
- The importer previously uploaded the full extracted path as the new object key, which turned logical files into directory-like paths in Supabase Storage.

## Implementation
- Keep the fix local to `backend/tools/import_snapshot_backup.py`.
- In `_collect_storage_objects(...)`, detect the versioned snapshot layout by checking whether the final path segment is a UUID blob version.
- When that layout is detected, strip the final UUID segment from the target key and upload the blob under the logical object key only.
- Leave direct, non-versioned layouts unchanged.

## Tests
- Add regression tests for JPG and PDF snapshot paths shaped as `submissions/<logical-key>/<version-uuid>`.
- Keep the existing tests for direct extracted layouts (`submissions/<file>`) green.
- Verify with:
  - `pytest -q backend/tests/migration/test_import_snapshot_backup.py`

## Assumptions
- Broken local objects do not need in-place repair; a fresh `make import-snapshot` after this fix is the intended recovery path.
- Snapshot version blob identifiers are UUIDs in the currently supported archive format.
