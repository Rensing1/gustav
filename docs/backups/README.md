# Legacy Storage Backups

This folder hosts artifacts extracted from the legacy Supabase storage volume.  
`storage_blobs_2025-10-28_13-13-13.tar.gz` contains the complete `section_materials` and `submissions` buckets (≈447 MB) and matches the metadata recorded in the legacy database backups (`storage.objects`).  

Usage notes:
- Extract to a staging directory before running migration tooling, e.g. `tar -xzf storage_blobs_2025-10-28_13-13-13.tar.gz -C /tmp/legacy_storage`.
- Keep the archive under version control only while coordinating the migration. To avoid repository bloat once the migration is stable, move it to a dedicated artifact store and update documentation accordingly.
